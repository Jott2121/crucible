import io
import sys

import pytest

from idna.cli import _build_parser, _convert_one, _iter_stdin, _looks_like_alabel, main
from idna.package_data import __version__


# ---------------------------------------------------------------------------
# _looks_like_alabel
# ---------------------------------------------------------------------------

def test_looks_like_alabel_plain_ascii_domain():
    assert _looks_like_alabel("example.com") is False


def test_looks_like_alabel_single_alabel():
    assert _looks_like_alabel("xn--nxasmq6b") is True


def test_looks_like_alabel_alabel_within_multi_label_domain():
    assert _looks_like_alabel("www.xn--nxasmq6b.com") is True


def test_looks_like_alabel_case_insensitive():
    assert _looks_like_alabel("XN--ABC.com") is True


def test_looks_like_alabel_empty_string():
    assert _looks_like_alabel("") is False


def test_looks_like_alabel_no_prefix_multi_label():
    assert _looks_like_alabel("a.b.c") is False


# ---------------------------------------------------------------------------
# _build_parser
# ---------------------------------------------------------------------------

def test_build_parser_prog_name():
    parser = _build_parser()
    assert parser.prog == "python -m idna"


def test_build_parser_defaults():
    parser = _build_parser()
    args = parser.parse_args([])
    assert args.domain == []
    assert args.mode is None
    assert args.strict is False


def test_build_parser_encode_flag():
    parser = _build_parser()
    args = parser.parse_args(["-e", "example.com"])
    assert args.mode == "encode"
    assert args.domain == ["example.com"]


def test_build_parser_decode_flag():
    parser = _build_parser()
    args = parser.parse_args(["--decode", "xn--abc"])
    assert args.mode == "decode"
    assert args.domain == ["xn--abc"]


def test_build_parser_strict_flag():
    parser = _build_parser()
    args = parser.parse_args(["--strict", "example.com"])
    assert args.strict is True


def test_build_parser_mutually_exclusive_encode_decode():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["-e", "-d", "example.com"])


def test_build_parser_multiple_domains():
    parser = _build_parser()
    args = parser.parse_args(["a.com", "b.com", "c.com"])
    assert args.domain == ["a.com", "b.com", "c.com"]


def test_build_parser_version(capsys):
    parser = _build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["--version"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"idna {__version__}"


# ---------------------------------------------------------------------------
# _iter_stdin
# ---------------------------------------------------------------------------

def test_iter_stdin_skips_blank_lines():
    stream = io.StringIO("a\n\nb\n   \nc\n")
    assert list(_iter_stdin(stream)) == ["a", "b", "c"]


def test_iter_stdin_empty_stream():
    stream = io.StringIO("")
    assert list(_iter_stdin(stream)) == []


def test_iter_stdin_only_whitespace_lines():
    stream = io.StringIO("  \n\n\t\n")
    assert list(_iter_stdin(stream)) == []


def test_iter_stdin_strips_whitespace():
    stream = io.StringIO("  hello  \n")
    assert list(_iter_stdin(stream)) == ["hello"]


# ---------------------------------------------------------------------------
# _convert_one
# ---------------------------------------------------------------------------

def test_convert_one_encode_success(capsys):
    result = _convert_one("pyth\u00f6n.org", "encode", True)
    assert result is True
    captured = capsys.readouterr()
    assert captured.out.strip() == "xn--pythn-mua.org"
    assert captured.err == ""


def test_convert_one_decode_success(capsys):
    result = _convert_one("xn--pythn-mua.org", "decode", True)
    assert result is True
    captured = capsys.readouterr()
    assert captured.out.strip() == "pyth\u00f6n.org"
    assert captured.err == ""


def test_convert_one_encode_failure_label_too_long(capsys):
    too_long_domain = "a" * 64 + ".com"
    result = _convert_one(too_long_domain, "encode", True)
    assert result is False
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "idna: encode failed for" in captured.err
    assert repr(too_long_domain) in captured.err


def test_convert_one_decode_failure_empty_alabel_content(capsys):
    result = _convert_one("xn--", "decode", True)
    assert result is False
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "idna: decode failed for" in captured.err
    assert repr("xn--") in captured.err


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def test_main_encode_default_mode(capsys):
    rc = main(["pyth\u00f6n.org"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "xn--pythn-mua.org"


def test_main_decode_default_mode(capsys):
    rc = main(["xn--pythn-mua.org"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "pyth\u00f6n.org"


def test_main_explicit_encode_flag(capsys):
    rc = main(["-e", "pyth\u00f6n.org"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "xn--pythn-mua.org"


def test_main_explicit_decode_flag(capsys):
    rc = main(["-d", "xn--pythn-mua.org"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "pyth\u00f6n.org"


def test_main_strict_flag_still_encodes(capsys):
    rc = main(["--strict", "pyth\u00f6n.org"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "xn--pythn-mua.org"


def test_main_multiple_domains_all_success(capsys):
    rc = main(["example.com", "python.org"])
    assert rc == 0
    captured = capsys.readouterr()
    lines = captured.out.strip().splitlines()
    assert lines == ["example.com", "python.org"]


def test_main_mixed_success_and_failure_returns_1(capsys):
    too_long_domain = "a" * 64 + ".com"
    rc = main(["pyth\u00f6n.org", too_long_domain])
    assert rc == 1
    captured = capsys.readouterr()
    assert "xn--pythn-mua.org" in captured.out
    assert "idna: encode failed for" in captured.err


def test_main_no_domain_returns_0_from_empty_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    rc = main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_main_reads_domain_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("pyth\u00f6n.org\n"))
    rc = main([])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "xn--pythn-mua.org"


def test_main_reads_multiple_domains_from_stdin_same_mode(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "stdin", io.StringIO("xn--pythn-mua.org\nxn--pythn-mua.org\n")
    )
    rc = main([])
    assert rc == 0
    captured = capsys.readouterr()
    lines = captured.out.strip().splitlines()
    assert lines == ["pyth\u00f6n.org", "pyth\u00f6n.org"]


def test_main_errors_when_no_domain_and_stdin_is_tty(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2

