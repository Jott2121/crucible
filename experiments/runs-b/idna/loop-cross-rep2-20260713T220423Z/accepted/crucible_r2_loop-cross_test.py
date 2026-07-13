import pytest

import idna.cli as cli


def test_parser_exposes_complete_documented_help_text():
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

    def action_for(option):
        return next(
            action for action in parser._actions if option in action.option_strings
        )

    assert action_for("--encode").help == "Encode the input to its ASCII A-label form."
    assert action_for("--decode").help == "Decode the input from its ASCII A-label form."
    assert (
        action_for("--strict").help
        == "Disable the default UTS #46 mapping and apply IDNA 2008 rules verbatim."
    )

    domain_action = next(action for action in parser._actions if action.dest == "domain")
    assert (
        domain_action.help
        == "One or more domain names to convert. Omit to read from stdin."
    )


def test_main_terminal_input_error_has_documented_message(monkeypatch, capsys):
    class TerminalStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", TerminalStdin())

    with pytest.raises(SystemExit) as excinfo:
        cli.main([])

    assert excinfo.value.code == 2
    assert capsys.readouterr().err.endswith(
        "python -m idna: error: a domain argument is required when stdin is a terminal\n"
    )


def test_encode_conversion_requests_lowercase_ascii_codec(monkeypatch, capsys):
    class EncodedDomain:
        def decode(self, encoding):
            assert encoding == "ascii"
            return "example.test"

    def fake_encode(domain, *, uts46):
        assert domain == "input.test"
        assert uts46 is True
        return EncodedDomain()

    monkeypatch.setattr(cli, "encode", fake_encode)

    assert cli._convert_one("input.test", "encode", True) is True
    assert capsys.readouterr().out == "example.test\n"


def test_alabel_detection_requests_lowercase_ascii_codec(monkeypatch):
    requested_encodings = []

    class Prefix:
        def decode(self, encoding):
            requested_encodings.append(encoding)
            return "xn--"

    monkeypatch.setattr(cli, "_alabel_prefix", Prefix())

    assert cli._looks_like_alabel("example.XN--bcher-kva") is True
    assert requested_encodings == ["ascii"]
