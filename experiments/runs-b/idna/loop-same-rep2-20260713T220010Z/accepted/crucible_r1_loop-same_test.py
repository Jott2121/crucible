import sys

import pytest

from idna import cli


# ---------------------------------------------------------------------------
# Description / help text checks (exact attribute values, not formatted text,
# to avoid any risk of line-wrapping by argparse's HelpFormatter).
# ---------------------------------------------------------------------------

def _find_action(actions, *, dest=None, option=None):
    for action in actions:
        if dest is not None and action.dest != dest:
            continue
        if option is not None and option not in action.option_strings:
            continue
        return action
    raise AssertionError("action not found")


def test_build_parser_description_exact():
    parser = cli._build_parser()
    expected_description = (
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
    assert parser.description == expected_description


def test_domain_positional_help_exact():
    parser = cli._build_parser()
    action = _find_action(parser._actions, dest="domain")
    assert action.help == "One or more domain names to convert. Omit to read from stdin."


def test_encode_flag_help_exact():
    parser = cli._build_parser()
    action = _find_action(parser._actions, option="-e")
    assert action.help == "Encode the input to its ASCII A-label form."


def test_decode_flag_help_exact():
    parser = cli._build_parser()
    action = _find_action(parser._actions, option="-d")
    assert action.help == "Decode the input from its ASCII A-label form."


def test_strict_flag_help_exact():
    parser = cli._build_parser()
    action = _find_action(parser._actions, dest="strict")
    assert action.help == "Disable the default UTS #46 mapping and apply IDNA 2008 rules verbatim."


# ---------------------------------------------------------------------------
# _convert_one must forward the exact uts46 value it receives to encode/decode.
# ---------------------------------------------------------------------------

def test_convert_one_forwards_uts46_true_to_encode(monkeypatch):
    calls = {}

    def fake_encode(domain, uts46=False):
        calls["args"] = (domain, uts46)
        return b"xn--fake"

    monkeypatch.setattr(cli, "encode", fake_encode)
    result = cli._convert_one("example.com", "encode", True)
    assert result is True
    assert calls["args"] == ("example.com", True)


def test_convert_one_forwards_uts46_false_to_encode(monkeypatch):
    calls = {}

    def fake_encode(domain, uts46=False):
        calls["args"] = (domain, uts46)
        return b"xn--fake"

    monkeypatch.setattr(cli, "encode", fake_encode)
    result = cli._convert_one("example.com", "encode", False)
    assert result is True
    assert calls["args"] == ("example.com", False)


def test_convert_one_forwards_uts46_to_decode(monkeypatch):
    calls = {}

    def fake_decode(domain, uts46=False):
        calls["args"] = (domain, uts46)
        return "example.com"

    monkeypatch.setattr(cli, "decode", fake_decode)
    result = cli._convert_one("xn--fake", "decode", True)
    assert result is True
    assert calls["args"] == ("xn--fake", True)


# ---------------------------------------------------------------------------
# main() must compute uts46 = not args.strict and pass exactly that value
# through, for every domain in the run.
# ---------------------------------------------------------------------------

def test_main_default_uses_uts46_true(monkeypatch):
    calls = []

    def fake_convert_one(domain, mode, uts46):
        calls.append((domain, mode, uts46))
        return True

    monkeypatch.setattr(cli, "_convert_one", fake_convert_one)
    ret = cli.main(["example.com"])
    assert ret == 0
    assert calls == [("example.com", "encode", True)]


def test_main_strict_uses_uts46_false(monkeypatch):
    calls = []

    def fake_convert_one(domain, mode, uts46):
        calls.append((domain, mode, uts46))
        return True

    monkeypatch.setattr(cli, "_convert_one", fake_convert_one)
    ret = cli.main(["--strict", "example.com"])
    assert ret == 0
    assert calls == [("example.com", "encode", False)]


# ---------------------------------------------------------------------------
# Error message for terminal stdin with no domain argument must match exactly.
# ---------------------------------------------------------------------------

class _FakeTtyStdin:
    def isatty(self):
        return True


def test_main_errors_with_expected_message_when_stdin_is_terminal(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", _FakeTtyStdin())
    with pytest.raises(SystemExit):
        cli.main([])
    captured = capsys.readouterr()
    assert "a domain argument is required when stdin is a terminal" in captured.err


# ---------------------------------------------------------------------------
# When encoding fails, the diagnostic message must use the word "encode"
# (the fallback mode selected when the input does not look like an alabel).
# ---------------------------------------------------------------------------

def test_main_encode_failure_reports_encode_mode(capsys):
    too_long_label = "a" * 64 + ".com"
    ret = cli.main([too_long_label])
    captured = capsys.readouterr()
    assert ret == 1
    assert "idna: encode failed for" in captured.err
