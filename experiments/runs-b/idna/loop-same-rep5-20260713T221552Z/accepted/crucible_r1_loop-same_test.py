import sys

import pytest

import idna.cli as cli
from idna.cli import _build_parser, _convert_one, main


def _find_action(parser, dest, const=None, positional=False):
    for action in parser._actions:
        if getattr(action, "dest", None) != dest:
            continue
        if positional and action.option_strings:
            continue
        if const is not None and getattr(action, "const", None) != const:
            continue
        return action
    raise AssertionError(f"action with dest={dest!r} const={const!r} not found")


def test_description_exact_text():
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


def test_encode_option_strings_and_help():
    parser = _build_parser()
    action = _find_action(parser, "mode", const="encode")
    assert action.option_strings == ["-e", "--encode"]
    assert action.help == "Encode the input to its ASCII A-label form."


def test_decode_option_strings_and_help():
    parser = _build_parser()
    action = _find_action(parser, "mode", const="decode")
    assert action.option_strings == ["-d", "--decode"]
    assert action.help == "Decode the input from its ASCII A-label form."


def test_strict_option_help():
    parser = _build_parser()
    action = _find_action(parser, "strict")
    assert action.help == "Disable the default UTS #46 mapping and apply IDNA 2008 rules verbatim."


def test_domain_positional_help():
    parser = _build_parser()
    action = _find_action(parser, "domain", positional=True)
    assert action.help == "One or more domain names to convert. Omit to read from stdin."


def test_convert_one_decode_passes_uts46(monkeypatch):
    captured = {}

    def fake_decode(domain, uts46=None):
        captured["domain"] = domain
        captured["uts46"] = uts46
        return "decoded-value"

    monkeypatch.setattr(cli, "decode", fake_decode)
    result = _convert_one("xn--something", "decode", False)
    assert result is True
    assert captured["domain"] == "xn--something"
    assert captured["uts46"] is False


def test_convert_one_decode_passes_uts46_true(monkeypatch):
    captured = {}

    def fake_decode(domain, uts46=None):
        captured["uts46"] = uts46
        return "decoded-value"

    monkeypatch.setattr(cli, "decode", fake_decode)
    _convert_one("xn--something", "decode", True)
    assert captured["uts46"] is True


def test_convert_one_encode_passes_uts46(monkeypatch):
    captured = {}

    def fake_encode(domain, uts46=None):
        captured["domain"] = domain
        captured["uts46"] = uts46
        return b"encoded-value"

    monkeypatch.setattr(cli, "encode", fake_encode)
    result = _convert_one("example.com", "encode", False)
    assert result is True
    assert captured["domain"] == "example.com"
    assert captured["uts46"] is False


def test_convert_one_encode_passes_uts46_true(monkeypatch):
    captured = {}

    def fake_encode(domain, uts46=None):
        captured["uts46"] = uts46
        return b"encoded-value"

    monkeypatch.setattr(cli, "encode", fake_encode)
    _convert_one("example.com", "encode", True)
    assert captured["uts46"] is True


def test_main_strict_flag_passes_uts46_false(monkeypatch):
    captured = {}

    def fake_encode(domain, uts46=None):
        captured["uts46"] = uts46
        return b"encoded-value"

    monkeypatch.setattr(cli, "encode", fake_encode)
    rc = main(["--strict", "example.com"])
    assert rc == 0
    assert captured["uts46"] is False


def test_main_no_strict_flag_passes_uts46_true(monkeypatch):
    captured = {}

    def fake_encode(domain, uts46=None):
        captured["uts46"] = uts46
        return b"encoded-value"

    monkeypatch.setattr(cli, "encode", fake_encode)
    rc = main(["example.com"])
    assert rc == 0
    assert captured["uts46"] is True


def test_main_encode_failure_message_uses_lowercase_encode(capsys):
    domain = "a" * 64  # single label too long, should fail encoding
    rc = main([domain])
    assert rc == 1
    captured = capsys.readouterr()
    expected_prefix = f"idna: encode failed for {domain!r}:"
    assert expected_prefix in captured.err
