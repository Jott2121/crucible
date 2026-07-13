"""Tests for idna.cli (the ``python -m idna`` command-line interface)."""

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
from idna.package_data import __version__


# ---------------------------------------------------------------------------
# _looks_like_alabel
# ---------------------------------------------------------------------------

def test_looks_like_alabel_plain_ascii():
    assert _looks_like_alabel("example.com") is False


def test_looks_like_alabel_simple_prefix():
    assert _looks_like_alabel("xn--nxasmq6b") is True


def test_looks_like_alabel_case_insensitive():
    assert _looks_like_alabel("XN--NXASMQ6B") is True


def test_looks_like_alabel_second_label_prefixed():
    assert _looks_like_alabel("example.xn--p1ai") is True


def test_looks_like_alabel_no_label_prefixed():
    assert _looks_like_alabel("www.example.com") is False


def test_looks_like_alabel_empty_string():
    assert _looks_like_alabel("") is False


def test_looks_like_alabel_prefix_not_at_start():
    # Contains "xn--" but does not start a label with it.
    assert _looks_like_alabel("notxn--example") is False


def test_looks_like_alabel_just_prefix():
    assert _looks_like_alabel("xn--") is True


# ---------------------------------------------------------------------------
# _build_parser
# ---------------------------------------------------------------------------

def test_parser_prog_name():
    parser = _build_parser()
    assert parser.prog == "python -m idna"


def test_parser_defaults_no_args():
    parser = _build_parser()
    args = parser.parse_args([])
    assert args.domain == []
    assert args.mode is None
    assert args.strict is False


def test_parser_encode_flag():
    parser = _build_parser()
    args = parser.parse_args(["-e", "example.com"])
    assert args.mode == "encode"
    assert args.domain == ["example.com"]


def test_parser_decode_flag_long_form():
    parser = _build_parser()
    args = parser.parse_args(["--decode", "xn--nxasmq6b"])
    assert args.mode == "decode"


def test_parser_strict_flag():
    parser = _build_parser()
    args = parser.parse_args(["--strict", "example.com"])
    assert args.strict is True


def test_parser_multiple_domains():
    parser = _build_parser()
    args = parser.parse_args(["a.com", "b.com", "c.com"])
    assert args.domain == ["a.com", "b.com", "c.com"]


def test_parser_mutually_exclusive_encode_decode():
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["-e", "-d", "example.com"])
    assert exc_info.value.code == 2


def test_parser_version(capsys):
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"idna {__version__}"


# ---------------------------------------------------------------------------
# _iter_stdin
# ---------------------------------------------------------------------------

def test_iter_stdin_strips_and_skips_blanks():
    stream = io.StringIO("  example.com  \n\n\t\nfoo.bar\n   \n")
    result = list(_iter_stdin(stream))
    assert result == ["example.com", "foo.bar"]


def test_iter_stdin_empty_stream():
    stream = io.StringIO("")
    assert list(_iter_stdin(stream)) == []


def test_iter_stdin_only_blank_lines():
    stream = io.StringIO("\n   \n\t\n")
    assert list(_iter_stdin(stream)) == []


def test_iter_stdin_preserves_order():
    stream = io.StringIO("first\nsecond\nthird\n")
    assert list(_iter_stdin(stream)) == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# _convert_one
# ---------------------------------------------------------------------------

def test_convert_one_encode_success(capsys):
    ok = _convert_one("ドメイン.テスト", "encode", True)
    assert ok is True
    captured = capsys.readouterr()
    assert captured.out == "xn--eckwd4c7c.xn--zckzah\n"
    assert captured.err == ""


def test_convert_one_decode_success(capsys):
    ok = _convert_one("xn--eckwd4c7c.xn--zckzah", "decode", True)
    assert ok is True
    captured = capsys.readouterr()
    assert captured.out == "ドメイン.テスト\n"
    assert captured.err == ""


def test_convert_one_encode_failure_label_too_long(capsys):
    long_label = "a" * 64  # exceeds the 63 octet limit for a DNS label
    ok = _convert_one(long_label, "encode", True)
    assert ok is False
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "idna: encode failed for" in captured.err
    assert repr(long_label) in captured.err


def test_convert_one_decode_failure_label_too_long(capsys):
    long_alabel = "xn--" + "a" * 64
    ok = _convert_one(long_alabel, "decode", True)
    assert ok is False
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "idna: decode failed for" in captured.err
    assert repr(long_alabel) in captured.err


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def test_main_encode_single_domain(capsys):
    rc = main(["-e", "ドメイン.テスト"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == "xn--eckwd4c7c.xn--zckzah\n"


def test_main_decode_single_domain(capsys):
    rc = main(["-d", "xn--eckwd4c7c.xn--zckzah"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == "ドメイン.テスト\n"


def test_main_auto_detect_decode_mode(capsys):
    rc = main(["xn--eckwd4c7c.xn--zckzah"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == "ドメイン.テスト\n"


def test_main_auto_detect_encode_mode(capsys):
    rc = main(["ドメイン.テスト"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == "xn--eckwd4c7c.xn--zckzah\n"


def test_main_multiple_domains_uniform_mode(capsys):
    rc = main(["xn--eckwd4c7c.xn--zckzah", "xn--eckwd4c7c.xn--zckzah"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == "ドメイン.テスト\nドメイン.テスト\n"


def test_main_failure_returns_nonzero(capsys):
    rc = main(["-e", "a" * 64])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "idna: encode failed for" in captured.err


def test_main_no_domain_no_tty_empty_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("   \n\n\t\n"))
    rc = main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_main_reads_from_piped_stdin(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "stdin", io.StringIO("ドメイン.テスト\n\nドメイン.テスト\n")
    )
    rc = main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == "xn--eckwd4c7c.xn--zckzah\nxn--eckwd4c7c.xn--zckzah\n"


def test_main_returns_zero_for_empty_args_list_when_domains_given():
    # sanity: passing explicit domain avoids the stdin branch entirely
    rc = main(["-d", "xn--eckwd4c7c.xn--zckzah"])
    assert rc == 0
