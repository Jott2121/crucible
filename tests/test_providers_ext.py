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
