import pytest

import idna.cli as cli


def test_convert_one_uses_lowercase_ascii_codec_name(monkeypatch, capsys):
    codec_names = []

    class EncodedDomain:
        def decode(self, encoding):
            codec_names.append(encoding)
            return "converted.example"

    def fake_encode(domain, uts46):
        assert domain == "example"
        assert uts46 is True
        return EncodedDomain()

    monkeypatch.setattr(cli, "encode", fake_encode)

    assert cli._convert_one("example", "encode", True) is True
    assert capsys.readouterr().out == "converted.example\n"
    assert codec_names == ["ascii"]


def test_looks_like_alabel_uses_lowercase_ascii_codec_name(monkeypatch):
    codec_names = []

    class Prefix:
        def decode(self, encoding):
            codec_names.append(encoding)
            return "xn--"

    monkeypatch.setattr(cli, "_alabel_prefix", Prefix())

    assert cli._looks_like_alabel("www.xn--bcher-kva.example") is True
    assert codec_names == ["ascii"]


def test_main_terminal_stdin_error_message(monkeypatch, capsys):
    class TerminalStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", TerminalStdin())

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2
    assert capsys.readouterr().err.endswith(
        "python -m idna: error: a domain argument is required when stdin is a terminal\n"
    )
