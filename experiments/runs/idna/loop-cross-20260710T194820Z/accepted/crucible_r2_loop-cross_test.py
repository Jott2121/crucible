import pytest

import idna.cli as cli


def test_convert_one_requests_ascii_decoding_from_encoded_result(monkeypatch, capsys):
    class CodecSensitiveResult:
        def decode(self, encoding):
            assert encoding == "ascii"
            return "xn--bcher-kva.example"

    def fake_encode(domain, uts46):
        assert domain == "bücher.example"
        assert uts46 is True
        return CodecSensitiveResult()

    monkeypatch.setattr(cli, "encode", fake_encode)

    assert cli._convert_one("bücher.example", "encode", True) is True
    assert capsys.readouterr().out == "xn--bcher-kva.example\n"


def test_looks_like_alabel_decodes_prefix_using_ascii(monkeypatch):
    class CodecSensitivePrefix:
        def decode(self, encoding):
            assert encoding == "ascii"
            return "xn--"

    monkeypatch.setattr(cli, "_alabel_prefix", CodecSensitivePrefix())

    assert cli._looks_like_alabel("www.XN--bcher-kva.example") is True


def test_main_terminal_stdin_error_has_documented_message(monkeypatch, capsys):
    class TerminalStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", TerminalStdin())

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2
    assert "error: a domain argument is required when stdin is a terminal" in capsys.readouterr().err
