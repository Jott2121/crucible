"""Tests for idna/cli.py"""
import io
import sys

import pytest

from idna.cli import (
    _looks_like_alabel,
    _build_parser,
    _iter_stdin,
    _convert_one,
    main,
)
from idna.package_data import __version__


# ---------------------------------------------------------------------------
# _looks_like_alabel
# ---------------------------------------------------------------------------

def test_looks_like_alabel_plain_ascii_domain():
    assert _looks_like_alabel("example.com") is False


def test_looks_like_alabel_with_xn_prefix():
    assert _looks_like_alabel("xn--nxasmq6b") is True


def test_looks_like_alabel_case_insensitive():
    assert _looks_like_alabel("XN--nxasmq6b") is True


def test_looks_like_alabel_nested_in_subdomain():
    assert _looks_like_alabel("www.xn--nxasmq6b.com") is True


def test_looks_like_alabel_empty_string():
    assert _looks_like_alabel("") is False


def test_looks_like_alabel_no_prefix_anywhere():
    assert _looks_like_alabel("a.b.c.example.org") is False


def test_looks_like_alabel_unicode_dot_separator():
    # \u3002 is the ideographic full stop, a valid IDNA dot separator
    assert _looks_like_alabel("xn--abc\u3002com") is True


def test_looks_like_alabel_unicode_dot_no_match():
    assert _looks_like_alabel("abc\u3002def") is False


# ---------------------------------------------------------------------------
# _build_parser
# ---------------------------------------------------------------------------

def test_parser_defaults_no_args():
    parser = _build_parser()
    args = parser.parse_args([])
    assert args.mode is None
    assert args.strict is False
    assert args.domain == []


def test_parser_encode_flag():
    parser = _build_parser()
    args = parser.parse_args(["-e", "test.com"])
    assert args.mode == "encode"
    assert args.domain == ["test.com"]


def test_parser_decode_flag_long_form():
    parser = _build_parser()
    args = parser.parse_args(["--decode", "xn--test"])
    assert args.mode == "decode"
    assert args.domain == ["xn--test"]


def test_parser_strict_flag():
    parser = _build_parser()
    args = parser.parse_args(["--strict", "test.com"])
    assert args.strict is True


def test_parser_multiple_domains():
    parser = _build_parser()
    args = parser.parse_args(["a.com", "b.com", "c.com"])
    assert args.domain == ["a.com", "b.com", "c.com"]


def test_parser_mutually_exclusive_encode_decode():
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["-e", "-d", "test.com"])
    assert exc_info.value.code == 2


def test_parser_version(capsys):
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert f"idna {__version__}" in out


# ---------------------------------------------------------------------------
# _iter_stdin
# ---------------------------------------------------------------------------

def test_iter_stdin_strips_and_skips_blank_lines():
    stream = io.StringIO("first\n\n  second  \n   \nthird\n")
    result = list(_iter_stdin(stream))
    assert result == ["first", "second", "third"]


def test_iter_stdin_empty_stream():
    stream = io.StringIO("")
    result = list(_iter_stdin(stream))
    assert result == []


def test_iter_stdin_only_blank_lines():
    stream = io.StringIO("\n   \n\t\n")
    result = list(_iter_stdin(stream))
    assert result == []


# ---------------------------------------------------------------------------
# _convert_one
# ---------------------------------------------------------------------------

def test_convert_one_encode_success(capsys):
    result = _convert_one("münchen", "encode", True)
    assert result is True
    out = capsys.readouterr().out
    assert out == "xn--mnchen-3ya\n"


def test_convert_one_decode_success(capsys):
    result = _convert_one("xn--mnchen-3ya", "decode", True)
    assert result is True
    out = capsys.readouterr().out
    assert out == "münchen\n"


def test_convert_one_ascii_passthrough_encode(capsys):
    result = _convert_one("example.com", "encode", True)
    assert result is True
    out = capsys.readouterr().out
    assert out == "example.com\n"


def test_convert_one_encode_failure_label_too_long(capsys):
    long_label = "a" * 64  # exceeds the 63 octet label length limit
    result = _convert_one(long_label, "encode", True)
    assert result is False
    err = capsys.readouterr().err
    assert "idna: encode failed for" in err
    assert long_label in err


def test_convert_one_decode_failure_invalid_alabel(capsys):
    result = _convert_one("xn--", "decode", True)
    assert result is False
    err = capsys.readouterr().err
    assert "idna: decode failed for" in err
    assert "xn--" in err


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def test_main_encode_from_positional_arg(capsys):
    ret = main(["example.com"])
    assert ret == 0
    out = capsys.readouterr().out
    assert out == "example.com\n"


def test_main_decode_auto_detected(capsys):
    ret = main(["xn--mnchen-3ya"])
    assert ret == 0
    out = capsys.readouterr().out
    assert out == "münchen\n"


def test_main_explicit_encode_flag(capsys):
    ret = main(["-e", "example.com"])
    assert ret == 0
    out = capsys.readouterr().out
    assert out == "example.com\n"


def test_main_explicit_decode_flag(capsys):
    ret = main(["-d", "xn--mnchen-3ya"])
    assert ret == 0
    out = capsys.readouterr().out
    assert out == "münchen\n"


def test_main_multiple_domains_uniform_mode(capsys):
    ret = main(["example.com", "test.org"])
    assert ret == 0
    out = capsys.readouterr().out
    assert out == "example.com\ntest.org\n"


def test_main_returns_1_on_failure(capsys):
    long_label = "b" * 64
    ret = main([long_label])
    assert ret == 1
    err = capsys.readouterr().err
    assert "idna: encode failed for" in err


def test_main_mixed_success_and_failure_returns_1(capsys):
    long_label = "c" * 64
    ret = main(["example.com", long_label])
    assert ret == 1
    captured = capsys.readouterr()
    assert "example.com" in captured.out
    assert "idna: encode failed for" in captured.err


def test_main_empty_domain_list_no_terminal_no_input(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    ret = main([])
    assert ret == 0
    out = capsys.readouterr().out
    assert out == ""


def test_main_reads_from_piped_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("example.com\ntest.org\n"))
    ret = main([])
    assert ret == 0
    out = capsys.readouterr().out
    assert out == "example.com\ntest.org\n"


def test_main_errors_when_stdin_is_terminal(monkeypatch):
    class FakeTTY(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", FakeTTY(""))
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_main_strict_flag_accepted(capsys):
    ret = main(["--strict", "example.com"])
    assert ret == 0
    out = capsys.readouterr().out
    assert out == "example.com\n"
