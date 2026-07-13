import pytest

from idna import cli


def test_parser_exposes_documented_description_options_and_help_text():
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

    encode_action = next(
        action for action in parser._actions if "--encode" in action.option_strings
    )
    decode_action = next(
        action for action in parser._actions if "--decode" in action.option_strings
    )
    strict_action = next(
        action for action in parser._actions if "--strict" in action.option_strings
    )
    domain_action = next(action for action in parser._actions if action.dest == "domain")

    assert encode_action.option_strings == ["-e", "--encode"]
    assert encode_action.help == "Encode the input to its ASCII A-label form."
    assert decode_action.help == "Decode the input from its ASCII A-label form."
    assert (
        strict_action.help
        == "Disable the default UTS #46 mapping and apply IDNA 2008 rules verbatim."
    )
    assert (
        domain_action.help
        == "One or more domain names to convert. Omit to read from stdin."
    )

    parsed = parser.parse_args(["--encode", "example.com"])
    assert parsed.mode == "encode"
    assert parsed.domain == ["example.com"]


def test_convert_one_applies_uts46_mapping_for_encode(capsys):
    success = cli._convert_one("Ａ.com", "encode", True)

    assert success is True
    assert capsys.readouterr().out == "a.com\n"


def test_convert_one_applies_uts46_mapping_for_decode(capsys):
    success = cli._convert_one("ｘｎ--bcher-kva.de", "decode", True)

    assert success is True
    assert capsys.readouterr().out == "bücher.de\n"


def test_main_selects_default_mode_and_passes_strict_uts46_setting(monkeypatch):
    calls = []

    def record_conversion(domain, mode, uts46):
        calls.append((domain, mode, uts46))
        return True

    monkeypatch.setattr(cli, "_convert_one", record_conversion)

    assert cli.main(["example.com"]) == 0
    assert calls == [("example.com", "encode", True)]

    calls.clear()
    assert cli.main(["--strict", "example.com"]) == 0
    assert calls == [("example.com", "encode", False)]


def test_main_reports_missing_domain_when_stdin_is_a_terminal(monkeypatch, capsys):
    class TerminalStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", TerminalStdin())

    with pytest.raises(SystemExit) as excinfo:
        cli.main([])

    assert excinfo.value.code == 2
    assert "a domain argument is required when stdin is a terminal" in capsys.readouterr().err
