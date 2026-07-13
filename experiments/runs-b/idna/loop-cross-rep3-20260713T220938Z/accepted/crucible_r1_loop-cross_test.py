import pytest

import idna.cli as cli


def test_parser_exposes_documented_description_options_and_help():
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
    assert decode_action.option_strings == ["-d", "--decode"]
    assert decode_action.help == "Decode the input from its ASCII A-label form."
    assert strict_action.help == (
        "Disable the default UTS #46 mapping and apply IDNA 2008 rules verbatim."
    )
    assert domain_action.help == (
        "One or more domain names to convert. Omit to read from stdin."
    )

    assert parser.parse_args(["--encode", "example.com"]).mode == "encode"
    assert parser.parse_args(["-d", "xn--bcher-kva.example"]).mode == "decode"


@pytest.mark.parametrize("uts46", [True, False])
def test_convert_one_forwards_uts46_to_decode(monkeypatch, capsys, uts46):
    seen = []

    def fake_decode(domain, *, uts46):
        seen.append((domain, uts46))
        return "decoded.example"

    monkeypatch.setattr(cli, "decode", fake_decode)

    assert cli._convert_one("input.example", "decode", uts46) is True
    assert seen == [("input.example", uts46)]
    assert capsys.readouterr().out == "decoded.example\n"


def test_main_reports_documented_error_when_terminal_stdin_has_no_domain(
    monkeypatch, capsys
):
    class TerminalStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", TerminalStdin())

    with pytest.raises(SystemExit) as excinfo:
        cli.main([])

    assert excinfo.value.code == 2
    assert "a domain argument is required when stdin is a terminal" in capsys.readouterr().err
