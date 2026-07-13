"""Tests for idna.cli (installed as the ``idna`` package's CLI module)."""

import io
import sys

import pytest

from idna.cli import (
    _build_parser,
    _convert_one,
    _iter_stdin,
    _looks_like_alabel,
    main,
)
from idna.package_data import __version__ as IDNA_VERSION


# ---------------------------------------------------------------------------
# _looks_like_alabel
# ---------------------------------------------------------------------------

def test_looks_like_alabel_plain_ascii_label_is_false():
    assert _looks_like_alabel("xn-abc") is False


def test_looks_like_alabel_single_label():
    assert _looks_like_alabel("xn--nxasmq6b") is True


def test_looks_like_alabel_plain_domain_is_false():
    assert _looks_like_alabel("example.com") is False


def test_looks_like_alabel_second_label_matches():
    assert _looks_like_alabel("www.xn--nxasmq6b.com") is True


def test_looks_like_alabel_case_insensitive():
    assert _looks_like_alabel("XN--nxasmq6b") is True


def test_looks_like_alabel_empty_string_is_false():
    assert _looks_like_alabel("") is False


def test_looks_like_alabel_unicode_dot_separator():
    assert _looks_like_alabel("xn--abc\u3002def") is True


def test_looks_like_alabel_unicode_dot_no_ace():
    assert _looks_like_alabel("abc\u3002def") is False


def test_looks_like_alabel_unicode_dot_second_label():
    assert _looks_like_alabel("abc\u3002xn--def") is True


# ---------------------------------------------------------------------------
# _build_parser
# ---------------------------------------------------------------------------

def test_build_parser_prog_name():
    parser = _build_parser()
    assert parser.prog == "python -m idna"


def test_build_parser_defaults():
    parser = _build_parser()
    args = parser.parse_args([])
    assert args.mode is None
    assert args.strict is False
    assert args.domain == []


def test_build_parser_encode_flag():
    parser = _build_parser()
    args = parser.parse_args(["-e", "example.com"])
    assert args.mode == "encode"
    assert args.domain == ["example.com"]


def test_build_parser_decode_flag_long_form():
    parser = _build_parser()
    args = parser.parse_args(["--decode", "example.com"])
    assert args.mode == "decode"


def test_build_parser_strict_flag():
    parser = _build_parser()
    args = parser.parse_args(["--strict", "example.com"])
    assert args.strict is True


def test_build_parser_multiple_domains():
    parser = _build_parser()
    args = parser.parse_args(["a.com", "b.com", "c.com"])
    assert args.domain == ["a.com", "b.com", "c.com"]


def test_build_parser_mutually_exclusive_raises():
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["-e", "-d", "example.com"])
    assert exc_info.value.code == 2


def test_build_parser_version(capsys):
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == f"idna {IDNA_VERSION}\n"


# ---------------------------------------------------------------------------
# _iter_stdin
# ---------------------------------------------------------------------------

def test_iter_stdin_strips_and_skips_blanks():
    stream = io.StringIO(" \n\nabc \n  ghi\n")
    assert list(_iter_stdin(stream)) == ["abc", "ghi"]


def test_iter_stdin_empty_stream():
    stream = io.StringIO("")
    assert list(_iter_stdin(stream)) == []


def test_iter_stdin_only_whitespace_lines():
    stream = io.StringIO("   \n\t\n")
    assert list(_iter_stdin(stream)) == []


# ---------------------------------------------------------------------------
# _convert_one
# ---------------------------------------------------------------------------

def test_convert_one_encode_ascii_domain(capsys):
    result = _convert_one("example.com", "encode", True)
    captured = capsys.readouterr()
    assert result is True
    assert captured.out == "example.com\n"
    assert captured.err == ""


def test_convert_one_decode_known_domain(capsys):
    domain = "xn--eckwd4c7c.xn--zckzah"
    result = _convert_one(domain, "decode", True)
    captured = capsys.readouterr()
    assert result is True
    assert captured.out == "\u30c9\u30e1\u30a4\u30f3.\u30c6\u30b9\u30c8\n"
    assert captured.err == ""


def test_convert_one_encode_label_too_long_fails(capsys):
    domain = "a" * 64
    result = _convert_one(domain, "encode", True)
    captured = capsys.readouterr()
    assert result is False
    assert captured.out == ""
    assert captured.err.startswith(f"idna: encode failed for {domain!r}:")


def test_convert_one_decode_label_too_long_fails(capsys):
    domain = "xn--" + "a" * 60  # total length 64 > max label length 63
    result = _convert_one(domain, "decode", True)
    captured = capsys.readouterr()
    assert result is False
    assert captured.err.startswith(f"idna: decode failed for {domain!r}:")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def test_main_encode_default_mode_from_positional_arg(capsys):
    rc = main(["example.com"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "example.com\n"


def test_main_decode_default_mode_from_positional_arg(capsys):
    rc = main(["xn--eckwd4c7c.xn--zckzah"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "\u30c9\u30e1\u30a4\u30f3.\u30c6\u30b9\u30c8\n"


def test_main_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == f"idna {IDNA_VERSION}\n"


def test_main_mutually_exclusive_flags_exit_two():
    with pytest.raises(SystemExit) as exc_info:
        main(["-e", "-d", "example.com"])
    assert exc_info.value.code == 2


def test_main_partial_failure_returns_one(capsys):
    long_label = "a" * 64
    rc = main(["example.com", long_label])
    captured = capsys.readouterr()
    assert rc == 1
    assert "example.com" in captured.out
    assert captured.err.startswith(f"idna: encode failed for {long_label!r}:")


def test_main_reads_from_stdin_when_no_domain_args(monkeypatch, capsys):
    fake_stdin = io.StringIO("example.com\nexample.org\n")
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "example.com\nexample.org\n"


def test_main_stdin_all_blank_lines_returns_zero_no_output(monkeypatch, capsys):
    fake_stdin = io.StringIO("\n\n   \n")
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""
    assert captured.err == ""


def test_main_stdin_empty_returns_zero(monkeypatch, capsys):
    fake_stdin = io.StringIO("")
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""


def test_main_terminal_stdin_without_domain_errors(monkeypatch):
    class FakeTTYStdin:
        def isatty(self):
            return True

        def __iter__(self):
            return iter([])

    monkeypatch.setattr(sys, "stdin", FakeTTYStdin())
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_main_stdin_forced_decode_mode(monkeypatch, capsys):
    fake_stdin = io.StringIO("xn--eckwd4c7c.xn--zckzah\n")
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    rc = main(["-d"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "\u30c9\u30e1\u30a4\u30f3.\u30c6\u30b9\u30c8\n"

