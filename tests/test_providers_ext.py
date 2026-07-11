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
