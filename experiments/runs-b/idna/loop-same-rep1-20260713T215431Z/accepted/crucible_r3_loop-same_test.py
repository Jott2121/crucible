import pytest
from idna import cli


def test_convert_one_uses_lowercase_ascii_decode(monkeypatch):
    """`_convert_one` must decode the encoded bytes using the literal
    string ``"ascii"`` (case-sensitive check via a fake bytes-like object).
    """
    captured = {}

    class FakeBytes:
        def decode(self, encoding):
            captured["encoding"] = encoding
            return "xn--nxasmq6b"

    def fake_encode(domain, uts46=True):
        return FakeBytes()

    monkeypatch.setattr(cli, "encode", fake_encode)

    result = cli._convert_one("münchen.de", "encode", True)

    assert result is True
    assert captured["encoding"] == "ascii"


def test_looks_like_alabel_uses_lowercase_ascii_decode(monkeypatch):
    """`_looks_like_alabel` must decode `_alabel_prefix` using the literal
    string ``"ascii"`` (case-sensitive check via a fake prefix object).
    """
    captured = {}

    class FakePrefix:
        def decode(self, encoding):
            captured["encoding"] = encoding
            return "xn--"

    monkeypatch.setattr(cli, "_alabel_prefix", FakePrefix())

    result = cli._looks_like_alabel("xn--nxasmq6b.de")

    assert result is True
    assert captured["encoding"] == "ascii"
