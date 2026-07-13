import pytest

import idna.cli as cli


# ---------------------------------------------------------------------------
# Parser description / help text exact-content checks
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


def test_domain_argument_help_exact_text():
    parser = cli._build_parser()
    domain_action = next(a for a in parser._actions if a.dest == "domain")
    assert domain_action.help == (
        "One or more domain names to convert. Omit to read from stdin."
    )


def test_encode_flag_option_strings_and_help():
    parser = cli._build_parser()
    encode_action = next(
        a for a in parser._actions if "--encode" in getattr(a, "option_strings", [])
    )
    assert encode_action.option_strings == ["-e", "--encode"]
    assert encode_action.help == "Encode the input to its ASCII A-label form."
    assert encode_action.const == "encode"
    assert encode_action.dest == "mode"


def test_decode_flag_option_strings_and_help():
    parser = cli._build_parser()
    decode_action = next(
        a for a in parser._actions if "--decode" in getattr(a, "option_strings", [])
    )
    assert decode_action.option_strings == ["-d", "--decode"]
    assert decode_action.help == "Decode the input from its ASCII A-label form."
    assert decode_action.const == "decode"
    assert decode_action.dest == "mode"


def test_strict_flag_help_exact_text():
    parser = cli._build_parser()
    strict_action = next(
        a for a in parser._actions if "--strict" in getattr(a, "option_strings", [])
    )
    assert strict_action.help == (
        "Disable the default UTS #46 mapping and apply IDNA 2008 rules verbatim."
    )


# ---------------------------------------------------------------------------
# _looks_like_alabel sanity checks
# ---------------------------------------------------------------------------

def test_looks_like_alabel_detects_prefixed_label():
    assert cli._looks_like_alabel("xn--nxasmq6b.com") is True


def test_looks_like_alabel_false_for_plain_domain():
    assert cli._looks_like_alabel("example.com") is False


# ---------------------------------------------------------------------------
# main()/_convert_one() correctly propagate the uts46 flag to encode/decode
# ---------------------------------------------------------------------------

def test_encode_receives_uts46_true_by_default(monkeypatch):
    captured = {}

    def fake_encode(domain, uts46=None):
        captured["uts46"] = uts46
        return b"xn--stub"

    monkeypatch.setattr(cli, "encode", fake_encode)
    rc = cli.main(["example.com"])
    assert rc == 0
    assert captured["uts46"] is True


def test_encode_receives_uts46_false_when_strict(monkeypatch):
    captured = {}

    def fake_encode(domain, uts46=None):
        captured["uts46"] = uts46
        return b"xn--stub"

    monkeypatch.setattr(cli, "encode", fake_encode)
    rc = cli.main(["--strict", "example.com"])
    assert rc == 0
    assert captured["uts46"] is False


def test_decode_receives_uts46_true_by_default(monkeypatch):
    captured = {}

    def fake_decode(domain, uts46=None):
        captured["uts46"] = uts46
        return "stub"

    monkeypatch.setattr(cli, "decode", fake_decode)
    rc = cli.main(["--decode", "xn--stub"])
    assert rc == 0
    assert captured["uts46"] is True


def test_decode_receives_uts46_false_when_strict(monkeypatch):
    captured = {}

    def fake_decode(domain, uts46=None):
        captured["uts46"] = uts46
        return "stub"

    monkeypatch.setattr(cli, "decode", fake_decode)
    rc = cli.main(["--strict", "--decode", "xn--stub"])
    assert rc == 0
    assert captured["uts46"] is False


# ---------------------------------------------------------------------------
# main() error message when stdin is a terminal and no domains supplied
# ---------------------------------------------------------------------------

def test_main_error_message_exact_text_when_stdin_is_tty(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])
    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "a domain argument is required when stdin is a terminal" in captured.err
