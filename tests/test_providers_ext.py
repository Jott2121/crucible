import pytest
from oracle_gate.providers import Usage

from crucible.providers_ext import FakeProvider, LongAnthropicProvider, TruncatedOutput, get_provider


def test_long_anthropic_raises_max_tokens():
    body = LongAnthropicProvider()._body("m", "sys", "user")
    assert body["max_tokens"] == 32000
    assert body["max_tokens"] == LongAnthropicProvider.output_cap


def test_truncated_output_str_is_exact():
    exc = TruncatedOutput(
        text="partial reply", usage=Usage(1000, 32000), model="claude-sonnet-5",
        prompt_sha256="a" * 64, cap=32000,
    )
    assert str(exc) == "truncated: output hit max_tokens cap (output_tokens=32000 >= max_tokens=32000)"
    assert exc.text == "partial reply"
    assert exc.usage == Usage(1000, 32000)
    assert exc.model == "claude-sonnet-5"
    assert exc.prompt_sha256 == "a" * 64
    assert exc.cap == 32000


def test_long_anthropic_uses_extended_read_timeout(monkeypatch):
    """A near-cap reply generates server-side for longer than oracle-gate's
    hardcoded 300s read timeout; the override must pass request_timeout through
    to urlopen or long critic rounds abort mid-generation (graph-guard
    loop-same, 2026-07-10)."""
    import io
    import json as _json
    import urllib.request as _ur

    seen = {}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        seen["timeout"] = timeout
        return _Resp(_json.dumps({
            "content": [{"text": "reply"}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }).encode())

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(_ur, "urlopen", fake_urlopen)
    text, usage = LongAnthropicProvider().complete_with_usage("sys", "user", model="m")
    assert seen["timeout"] == LongAnthropicProvider.request_timeout == 1200
    assert text == "reply" and usage == Usage(10, 20)


def test_fake_provider_scripts_replies():
    p = FakeProvider(["first", "second"])
    text, usage = p.complete_with_usage("s", "u")
    assert text == "first" and usage == Usage(1000, 500)
    text, _ = p.complete_with_usage("s", "u")
    assert text == "second"


def test_fake_provider_exhausted_raises():
    p = FakeProvider([])
    with pytest.raises(RuntimeError, match="exhausted"):
        p.complete_with_usage("s", "u")


def test_registry():
    assert get_provider("anthropic").__class__ is LongAnthropicProvider
    assert get_provider("openai").name == "openai"
    with pytest.raises(KeyError):
        get_provider("nope")


import json as _json


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _cli_envelope(text="pong", inp=12, out=5):
    # REALITY CHECK (2026-07-11 live probe, `claude -p --output-format json`):
    # the CLI emits a JSON ARRAY of stream events (system init, assistant
    # message, rate_limit_event, ...), not a single flat object. The brief's
    # canned single-object envelope does not match what the binary actually
    # prints -- confirmed with and without the operator's interactive zsh
    # `claude` function in the way (subprocess.run never sees that function
    # anyway). The event carrying the real fields is the last one, type=="result".
    return _json.dumps([
        {"type": "system", "subtype": "init", "session_id": "s"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}},
        {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}},
        {
            "type": "result", "subtype": "success", "is_error": False,
            "result": text, "usage": {"input_tokens": inp, "output_tokens": out},
            "total_cost_usd": 0.0, "session_id": "s",
        },
    ])


def test_claude_cli_provider_parses_text_and_usage(monkeypatch):
    from crucible.providers_ext import ClaudeCLIProvider
    calls = {}

    def fake_run(cmd, input=None, capture_output=True, text=True, timeout=None):
        calls["cmd"], calls["input"], calls["timeout"] = cmd, input, timeout
        return _FakeProc(stdout=_cli_envelope("hello", 100, 42))

    p = ClaudeCLIProvider(run=fake_run)
    reply, usage = p.complete_with_usage("SYS", "USER", model="claude-sonnet-5")
    assert reply == "hello"
    assert usage == Usage(100, 42)
    assert calls["cmd"][0] == "claude" and "-p" in calls["cmd"]
    assert "--output-format" in calls["cmd"] and "json" in calls["cmd"]
    assert "claude-sonnet-5" in calls["cmd"]
    assert calls["input"] == "USER"          # user prompt via stdin, never argv
    assert "SYS" in calls["cmd"]             # system prompt via flag
    assert calls["timeout"] == ClaudeCLIProvider.request_timeout == 1200


def test_claude_cli_provider_error_paths(monkeypatch):
    from crucible.providers_ext import ClaudeCLIProvider
    p_exit = ClaudeCLIProvider(run=lambda *a, **k: _FakeProc(returncode=1, stderr="boom"))
    with pytest.raises(RuntimeError, match="boom"):
        p_exit.complete_with_usage("s", "u")
    p_json = ClaudeCLIProvider(run=lambda *a, **k: _FakeProc(stdout="not json"))
    with pytest.raises(RuntimeError, match="envelope"):
        p_json.complete_with_usage("s", "u")

    def raise_fnf(*a, **k):
        raise FileNotFoundError("claude")

    p_missing = ClaudeCLIProvider(run=raise_fnf)
    with pytest.raises(RuntimeError, match="claude"):
        p_missing.complete_with_usage("s", "u")


def test_claude_cli_provider_is_error_envelope_fails_loud():
    from crucible.providers_ext import ClaudeCLIProvider
    # array-shaped, matching the live probe: the result event carries is_error.
    env = _json.dumps([
        {"type": "system", "subtype": "init"},
        {"type": "result", "is_error": True, "result": "over quota",
         "usage": {"input_tokens": 1, "output_tokens": 1}},
    ])
    p = ClaudeCLIProvider(run=lambda *a, **k: _FakeProc(stdout=env))
    with pytest.raises(RuntimeError, match="over quota"):
        p.complete_with_usage("s", "u")


def test_claude_cli_provider_array_envelope_missing_result_event_fails_loud():
    """Defensive: a stream with no type=='result' event (e.g. truncated output,
    process killed mid-stream) must fail loud, not silently return empty text."""
    from crucible.providers_ext import ClaudeCLIProvider
    env = _json.dumps([{"type": "system", "subtype": "init"}])
    p = ClaudeCLIProvider(run=lambda *a, **k: _FakeProc(stdout=env))
    with pytest.raises(RuntimeError, match="envelope"):
        p.complete_with_usage("s", "u")


def test_billing_attrs():
    from crucible.providers_ext import ClaudeCLIProvider
    assert ClaudeCLIProvider.billing == "max-plan"
    # absent attr means "api" -- the convention Task 2's meta stamping reads
    assert getattr(LongAnthropicProvider, "billing", "api") == "api"
    assert getattr(get_provider("openai"), "billing", "api") == "api"


def test_registry_has_claude_cli():
    from crucible.providers_ext import ClaudeCLIProvider
    assert get_provider("claude-cli").__class__ is ClaudeCLIProvider
