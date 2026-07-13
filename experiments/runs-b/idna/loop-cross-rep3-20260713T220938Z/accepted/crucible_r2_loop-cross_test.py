import sys

import pytest

import idna.cli as cli


def test_convert_one_decodes_encoded_result_using_lowercase_ascii(monkeypatch, capsys):
    calls = []

    class EncodedDomain:
        def decode(self, encoding):
            calls.append(encoding)
            return "example.com"

    monkeypatch.setattr(cli, "encode", lambda domain, uts46: EncodedDomain())

    assert cli._convert_one("example.com", "encode", True) is True
    assert calls == ["ascii"]
    assert capsys.readouterr().out == "example.com\n"


def test_looks_like_alabel_decodes_prefix_with_lowercase_ascii(monkeypatch):
    calls = []

    class Prefix:
        def decode(self, encoding):
            calls.append(encoding)
            return "xn--"

    monkeypatch.setattr(cli, "_alabel_prefix", Prefix())

    assert cli._looks_like_alabel("www.XN--bcher-kva.example") is True
    assert calls == ["ascii"]


def test_main_terminal_stdin_requires_domain_with_original_error_message(monkeypatch, capsys):
    class TerminalStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", TerminalStdin())

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2
    assert capsys.readouterr().err.splitlines()[-1] == (
        "python -m idna: error: a domain argument is required when stdin is a terminal"
    )
