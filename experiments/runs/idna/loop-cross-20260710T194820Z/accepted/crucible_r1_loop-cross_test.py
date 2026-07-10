import io

import pytest

import idna.cli as cli


def test_parser_exposes_documented_interface_and_help_text():
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

    assert parser.prog == "python -m idna"
    assert parser.description == expected_description

    actions = {action.dest: action for action in parser._actions}
    assert actions["domain"].help == (
        "One or more domain names to convert. Omit to read from stdin."
    )
    assert actions["strict"].help == (
        "Disable the default UTS #46 mapping and apply IDNA 2008 rules verbatim."
    )

    mode_actions = [
        action
        for group in parser._mutually_exclusive_groups
        for action in group._group_actions
    ]
    encode_action = next(action for action in mode_actions if action.const == "encode")
    decode_action = next(action for action in mode_actions if action.const == "decode")

    assert "--encode" in encode_action.option_strings
    assert encode_action.help == "Encode the input to its ASCII A-label form."
    assert decode_action.help == "Decode the input from its ASCII A-label form."
    assert parser.parse_args(["--encode", "example.com"]).mode == "encode"


@pytest.mark.parametrize("mode, uts46", [("encode", True), ("decode", False)])
def test_convert_one_forwards_uts46_setting_to_selected_converter(
    monkeypatch, capsys, mode, uts46
):
    calls = []

    def fake_encode(domain, *, uts46):
        calls.append(("encode", domain, uts46))
        return b"encoded.example"

    def fake_decode(domain, *, uts46):
        calls.append(("decode", domain, uts46))
        return "decoded.example"

    monkeypatch.setattr(cli, "encode", fake_encode)
    monkeypatch.setattr(cli, "decode", fake_decode)

    assert cli._convert_one("input.example", mode, uts46) is True

    expected_output = "encoded.example\n" if mode == "encode" else "decoded.example\n"
    assert capsys.readouterr().out == expected_output
    assert calls == [(mode, "input.example", uts46)]


@pytest.mark.parametrize(
    ("argv", "expected_uts46"),
    [
        (["example.com"], True),
        (["--strict", "example.com"], False),
    ],
)
def test_main_uses_default_mapping_unless_strict_is_requested(
    monkeypatch, argv, expected_uts46
):
    calls = []

    def fake_convert(domain, mode, uts46):
        calls.append((domain, mode, uts46))
        return True

    monkeypatch.setattr(cli, "_convert_one", fake_convert)

    assert cli.main(argv) == 0
    assert calls == [("example.com", "encode", expected_uts46)]


def test_main_terminal_stdin_requires_domain_with_documented_error(
    monkeypatch, capsys
):
    class TerminalInput(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", TerminalInput(""))

    with pytest.raises(SystemExit) as excinfo:
        cli.main([])

    assert excinfo.value.code == 2
    assert "a domain argument is required when stdin is a terminal" in capsys.readouterr().err
