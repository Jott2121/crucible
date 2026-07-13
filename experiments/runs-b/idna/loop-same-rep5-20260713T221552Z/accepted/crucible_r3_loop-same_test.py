import pytest
import idna.cli as cli


def test_convert_one_decodes_ascii_lowercase(monkeypatch, capsys):
    """_convert_one must call bytes.decode with the lowercase 'ascii'
    codec name (case matters for asserting the exact literal used,
    even though the codec lookup itself is case-insensitive)."""
    recorded = []

    class FakeEncoded:
        def decode(self, encoding):
            recorded.append(encoding)
            return "xn--fake"

    def fake_encode(domain, uts46=True):
        return FakeEncoded()

    monkeypatch.setattr(cli, "encode", fake_encode)

    ok = cli._convert_one("example.com", "encode", True)

    assert ok is True
    assert recorded == ["ascii"]


def test_looks_like_alabel_decodes_prefix_with_ascii_lowercase(monkeypatch):
    """_looks_like_alabel must decode the alabel prefix bytes using the
    lowercase 'ascii' codec name literal."""
    recorded = []

    class FakePrefix:
        def decode(self, encoding):
            recorded.append(encoding)
            return "xn--"

    monkeypatch.setattr(cli, "_alabel_prefix", FakePrefix())

    result = cli._looks_like_alabel("xn--nxasmq6b.example.com")

    assert recorded == ["ascii"]
    # sanity check on functional behavior as well
    assert result is True
