import io
import sys

import pytest

from idna import cli
from idna.package_data import __version__ as idna_version


# ---------------------------------------------------------------------------
# _looks_like_alabel
# ---------------------------------------------------------------------------

def test_looks_like_alabel_true_simple():
    assert cli._looks_like_alabel("xn--nxasmq6b") is True


def test_looks_like_alabel_true_case_insensitive():
    assert cli._looks_like_alabel("XN--nxasmq6b") is True


def test_looks_like_alabel_true_in_subdomain():
    assert cli._looks_like_alabel("www.xn--nxasmq6b.com") is True


def test_looks_like_alabel_false_plain_domain():
    assert cli._looks_like_alabel("example.com") is False


def test_looks_like_alabel_false_empty_string():
    assert cli._looks_like_alabel("") is False


def test_looks_like_alabel_false_partial_prefix():
    assert cli._looks_like_alabel("xn-notquite") is False


# ---------------------------------------------------------------------------
# _build_parser
# ---------------------------------------------------------------------------

def test_build_parser_prog_name():
    parser = cli._build_parser()
    assert parser.prog == "python -m idna"


def test_build_parser_defaults():
    parser = cli._build_parser()
    args = parser.parse_args([])
    assert args.mode is None
    assert args.strict is False
    assert args.domain == []


def test_build_parser_encode_flag_short():
    parser = cli._build_parser()
    args = parser.parse_args(["-e"])
    assert args.mode == "encode"


def test_build_parser_encode_flag_long():
    parser = cli._build_parser()
    args = parser.parse_args(["--encode"])
    assert args.mode == "encode"


def test_build_parser_decode_flag_short():
    parser = cli._build_parser()
    args = parser.parse_args(["-d"])
    assert args.mode == "decode"


def test_build_parser_decode_flag_long():
    parser = cli._build_parser()
    args = parser.parse_args(["--decode"])
    assert args.mode == "decode"


def test_build_parser_strict_flag():
    parser = cli._build_parser()
    args = parser.parse_args(["--strict"])
    assert args.strict is True


def test_build_parser_mutually_exclusive_raises():
    parser = cli._build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["-e", "-d"])
    assert excinfo.value.code == 2


def test_build_parser_domain_positional_multiple():
    parser = cli._build_parser()
    args = parser.parse_args(["example.com", "test.com"])
    assert args.domain == ["example.com", "test.com"]


def test_build_parser_version_exit_code_and_output(capsys):
    parser = cli._build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["--version"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"idna {idna_version}"


# ---------------------------------------------------------------------------
# _iter_stdin
# ---------------------------------------------------------------------------

def test_iter_stdin_filters_blank_lines_and_strips():
    stream = io.StringIO("a\n\n  b  \n\nc\n")
    result = list(cli._iter_stdin(stream))
    assert result == ["a", "b", "c"]


def test_iter_stdin_empty_stream():
    stream = io.StringIO("")
    result = list(cli._iter_stdin(stream))
    assert result == []


def test_iter_stdin_all_blank_lines():
    stream = io.StringIO("\n\n   \n\t\n")
    result = list(cli._iter_stdin(stream))
    assert result == []


# ---------------------------------------------------------------------------
# _convert_one
# ---------------------------------------------------------------------------

def test_convert_one_encode_success(capsys):
    result = cli._convert_one("münchen", "encode", True)
    captured = capsys.readouterr()
    assert result is True
    assert captured.out.strip() == "xn--mnchen-3ya"
    assert captured.err == ""


def test_convert_one_decode_success(capsys):
    result = cli._convert_one("xn--mnchen-3ya", "decode", True)
    captured = capsys.readouterr()
    assert result is True
    assert captured.out.strip() == "münchen"
    assert captured.err == ""


def test_convert_one_encode_failure_label_too_long(capsys):
    too_long_label = "a" * 64  # exceeds the 63-octet label limit
    result = cli._convert_one(too_long_label, "encode", True)
    captured = capsys.readouterr()
    assert result is False
    assert captured.out == ""
    assert "idna: encode failed for" in captured.err
    assert repr(too_long_label) in captured.err


def test_convert_one_decode_failure_label_too_long(capsys):
    too_long_alabel = "xn--" + "a" * 60  # total length 64, exceeds the limit
    result = cli._convert_one(too_long_alabel, "decode", True)
    captured = capsys.readouterr()
    assert result is False
    assert captured.out == ""
    assert "idna: decode failed for" in captured.err
    assert repr(too_long_alabel) in captured.err


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def test_main_encode_single_domain(capsys):
    ret = cli.main(["-e", "münchen"])
    captured = capsys.readouterr()
    assert ret == 0
    assert captured.out.strip() == "xn--mnchen-3ya"


def test_main_decode_single_domain(capsys):
    ret = cli.main(["-d", "xn--mnchen-3ya"])
    captured = capsys.readouterr()
    assert ret == 0
    assert captured.out.strip() == "münchen"


def test_main_infers_decode_mode_from_xn_prefix(capsys):
    ret = cli.main(["xn--mnchen-3ya"])
    captured = capsys.readouterr()
    assert ret == 0
    assert captured.out.strip() == "münchen"


def test_main_infers_encode_mode_without_xn_prefix(capsys):
    ret = cli.main(["münchen"])
    captured = capsys.readouterr()
    assert ret == 0
    assert captured.out.strip() == "xn--mnchen-3ya"


def test_main_multiple_domains_same_inferred_mode(capsys):
    ret = cli.main(["münchen", "münchen"])
    captured = capsys.readouterr()
    assert ret == 0
    lines = captured.out.strip().splitlines()
    assert lines == ["xn--mnchen-3ya", "xn--mnchen-3ya"]


def test_main_single_failure_returns_one(capsys):
    too_long_label = "a" * 64
    ret = cli.main(["-e", too_long_label])
    captured = capsys.readouterr()
    assert ret == 1
    assert captured.out == ""
    assert "idna: encode failed for" in captured.err


def test_main_mixed_success_and_failure_returns_one(capsys):
    too_long_label = "a" * 64
    ret = cli.main(["-e", "münchen", too_long_label])
    captured = capsys.readouterr()
    assert ret == 1
    assert "xn--mnchen-3ya" in captured.out
    assert "idna: encode failed for" in captured.err


def test_main_no_domain_no_stdin_input_returns_zero(monkeypatch, capsys):
    class _FakeStdin(io.StringIO):
        def isatty(self):
            return False

    monkeypatch.setattr(sys, "stdin", _FakeStdin(""))
    ret = cli.main([])
    captured = capsys.readouterr()
    assert ret == 0
    assert captured.out == ""


def test_main_reads_domain_from_piped_stdin(monkeypatch, capsys):
    class _FakeStdin(io.StringIO):
        def isatty(self):
            return False

    monkeypatch.setattr(sys, "stdin", _FakeStdin("münchen\n"))
    ret = cli.main([])
    captured = capsys.readouterr()
    assert ret == 0
    assert captured.out.strip() == "xn--mnchen-3ya"


def test_main_stdin_is_terminal_with_no_domain_errors(monkeypatch):
    class _TTYStdin(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", _TTYStdin(""))
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2


def test_main_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"idna {idna_version}"

