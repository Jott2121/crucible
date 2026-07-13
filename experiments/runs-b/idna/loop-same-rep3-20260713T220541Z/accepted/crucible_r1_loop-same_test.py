import sys

import pytest

from idna import cli
from idna.cli import _build_parser, _convert_one, main


def test_parser_description_exact_text():
    parser = _build_parser()
    expected = (
        "Convert a domain name between its Unicode (U-label) and "
        "ASCII-compatible (A-label) forms. With no mode flag, the "
        "direction is chosen from the first input — if it contains "
        "an xn-- label the stream is decoded, otherwise it is "
        "encoded — and the same mode is applied to every remaining "
        "input. UTS #46 mapping is applied by default; pass "
        "--strict to disable it. When no domains are given on the "
        "command line and stdin is piped, one domain per line is "
        "read from stdin."
    )
    assert parser.description == expected


def test_encode_option_flags_and_help():
    parser = _build_parser()
    action = next(a for a in parser._actions if getattr(a, "const", None) == "encode")
    assert set(action.option_strings) == {"-e", "--encode"}
    assert action.help == "Encode the input to its ASCII A-label form."


def test_decode_option_flags_and_help():
    parser = _build_parser()
    action = next(a for a in parser._actions if getattr(a, "const", None) == "decode")
    assert set(action.option_strings) == {"-d", "--decode"}
    assert action.help == "Decode the input from its ASCII A-label form."


def test_strict_option_help():
    parser = _build_parser()
    action = next(a for a in parser._actions if "--strict" in a.option_strings)
    assert action.help == "Disable the default UTS #46 mapping and apply IDNA 2008 rules verbatim."


def test_domain_positional_help():
    parser = _build_parser()
    action = next(a for a in parser._actions if a.dest == "domain")
    assert action.help == "One or more domain names to convert. Omit to read from stdin."


def test_encode_flag_parses_correctly():
    parser = _build_parser()
    args = parser.parse_args(["--encode", "example.com"])
    assert args.mode == "encode"
    args2 = parser.parse_args(["-e", "example.com"])
    assert args2.mode == "encode"


def test_decode_flag_parses_correctly():
    parser = _build_parser()
    args = parser.parse_args(["--decode", "xn--example"])
    assert args.mode == "decode"
    args2 = parser.parse_args(["-d", "xn--example"])
    assert args2.mode == "decode"


def test_convert_one_decode_passes_exact_uts46_flag(monkeypatch, capsys):
    calls = {}

    def fake_decode(domain, uts46=None):
        calls["uts46"] = uts46
        return "decoded-result"

    monkeypatch.setattr(cli, "decode", fake_decode)

    result = _convert_one("xn--test", "decode", True)

    assert result is True
    assert calls["uts46"] is True
    captured = capsys.readouterr()
    assert captured.out.strip() == "decoded-result"


def test_convert_one_decode_passes_false_uts46_flag(monkeypatch, capsys):
    calls = {}

    def fake_decode(domain, uts46=None):
        calls["uts46"] = uts46
        return "decoded-result-2"

    monkeypatch.setattr(cli, "decode", fake_decode)

    result = _convert_one("xn--test", "decode", False)

    assert result is True
    assert calls["uts46"] is False
    captured = capsys.readouterr()
    assert captured.out.strip() == "decoded-result-2"


def test_convert_one_encode_passes_exact_uts46_flag(monkeypatch, capsys):
    calls = {}

    def fake_encode(domain, uts46=None):
        calls["uts46"] = uts46
        return b"xn--fake"

    monkeypatch.setattr(cli, "encode", fake_encode)

    result = _convert_one("example.com", "encode", False)

    assert result is True
    assert calls["uts46"] is False
    captured = capsys.readouterr()
    assert captured.out.strip() == "xn--fake"


def test_main_stdin_terminal_error_message(monkeypatch, capsys):
    class FakeStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", FakeStdin())

    with pytest.raises(SystemExit):
        main([])

    captured = capsys.readouterr()
    assert "a domain argument is required when stdin is a terminal" in captured.err
