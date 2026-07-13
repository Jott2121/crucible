import sys
import pytest

from idna import cli


def test_convert_one_encode_uses_lowercase_ascii_codec(monkeypatch):
    """_convert_one must decode the encoded bytes using the exact
    codec name 'ascii' (lowercase), not 'ASCII'."""
    recorded = {}

    class Recorder(bytes):
        def decode(self, encoding="utf-8", errors="strict"):
            recorded["encoding"] = encoding
            return super().decode(encoding, errors)

    def fake_encode(domain, uts46=True):
        return Recorder(b"example.com")

    monkeypatch.setattr(cli, "encode", fake_encode)

    result = cli._convert_one("example.com", "encode", True)

    assert result is True
    assert recorded.get("encoding") == "ascii"


def test_looks_like_alabel_uses_lowercase_ascii_codec(monkeypatch):
    """_looks_like_alabel must decode the ACE prefix bytes using the
    exact codec name 'ascii' (lowercase), not 'ASCII'."""
    recorded = {}

    class Recorder(bytes):
        def decode(self, encoding="utf-8", errors="strict"):
            recorded["encoding"] = encoding
            return super().decode(encoding, errors)

    monkeypatch.setattr(cli, "_alabel_prefix", Recorder(b"xn--"))

    result = cli._looks_like_alabel("xn--exampl-gva.com")

    assert result is True
    assert recorded.get("encoding") == "ascii"


def test_main_error_message_when_stdin_is_terminal(monkeypatch, capsys):
    """When no domains are given and stdin is a terminal, main() should
    report the exact expected error message (not a mutated/quoted one)."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    with pytest.raises(SystemExit):
        cli.main([])

    captured = capsys.readouterr()
    expected_message = "a domain argument is required when stdin is a terminal"
    assert expected_message in captured.err
    # Ensure it's not the mutated/quoted variant with XX markers around it
    assert "XXa domain argument" not in captured.err
