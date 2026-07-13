import sys

import pytest

from idna import cli


# ---------------------------------------------------------------------------
# Description / help text mutants (many text-only diffs collapse into these
# two exact-match assertions).
# ---------------------------------------------------------------------------

def test_parser_description_exact_text():
    parser = cli._build_parser()
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


def test_parser_help_texts_exact():
    parser = cli._build_parser()
    texts = {}
    for action in parser._actions:
        if action.option_strings:
            texts[action.option_strings[0]] = action.help
        elif action.dest == "domain":
            texts["domain"] = action.help

    assert texts["-e"] == "Encode the input to its ASCII A-label form."
    assert texts["-d"] == "Decode the input from its ASCII A-label form."
    assert texts["--strict"] == (
        "Disable the default UTS #46 mapping and apply IDNA 2008 rules verbatim."
    )
    assert texts["domain"] == (
        "One or more domain names to convert. Omit to read from stdin."
    )


def test_encode_long_flag_still_supported():
    parser = cli._build_parser()
    args = parser.parse_args(["--encode", "example.com"])
    assert args.mode == "encode"
    assert args.domain == ["example.com"]


# ---------------------------------------------------------------------------
# _convert_one argument-forwarding mutants
# ---------------------------------------------------------------------------

def test_convert_one_forwards_uts46_to_decode(monkeypatch, capsys):
    captured = {}

    def fake_decode(domain, uts46):
        captured["domain"] = domain
        captured["uts46"] = uts46
        return "RESULT"

    monkeypatch.setattr(cli, "decode", fake_decode)

    ok = cli._convert_one("example.com", "decode", False)

    out = capsys.readouterr().out
    assert ok is True
    assert captured == {"domain": "example.com", "uts46": False}
    assert out == "RESULT\n"


def test_convert_one_forwards_uts46_to_encode(monkeypatch, capsys):
    captured = {}

    class FakeBytes:
        def __init__(self, s):
            self._s = s

        def decode(self, encoding):
            captured["encoding"] = encoding
            return self._s

    def fake_encode(domain, uts46):
        captured["domain"] = domain
        captured["uts46"] = uts46
        return FakeBytes("xn--result")

    monkeypatch.setattr(cli, "encode", fake_encode)

    ok = cli._convert_one("exämple.com", "encode", True)

    out = capsys.readouterr().out
    assert ok is True
    assert captured["domain"] == "exämple.com"
    assert captured["uts46"] is True
    assert captured["encoding"] == "ascii"
    assert out == "xn--result\n"


# ---------------------------------------------------------------------------
# main() uts46 propagation mutants
# ---------------------------------------------------------------------------

class _FakeBytesResult:
    def __init__(self, s):
        self._s = s

    def decode(self, encoding):
        return self._s


def test_main_default_uts46_is_true(monkeypatch):
    captured = {}

    def fake_encode(domain, uts46):
        captured["uts46"] = uts46
        return _FakeBytesResult("xn--fake")

    monkeypatch.setattr(cli, "encode", fake_encode)

    ret = cli.main(["example.com"])

    assert ret == 0
    assert captured["uts46"] is True


def test_main_strict_flag_sets_uts46_false(monkeypatch):
    captured = {}

    def fake_encode(domain, uts46):
        captured["uts46"] = uts46
        return _FakeBytesResult("xn--fake")

    monkeypatch.setattr(cli, "encode", fake_encode)

    ret = cli.main(["--strict", "example.com"])

    assert ret == 0
    assert captured["uts46"] is False


# ---------------------------------------------------------------------------
# parser.error message mutant
# ---------------------------------------------------------------------------

class _FakeTTYStdin:
    def isatty(self):
        return True


def test_main_reports_specific_error_when_tty_and_no_domain(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", _FakeTTYStdin())

    with pytest.raises(SystemExit):
        cli.main([])

    err = capsys.readouterr().err
    assert "a domain argument is required when stdin is a terminal" in err
