import io

import pytest

from idna.cli import _build_parser, _convert_one, _iter_stdin, _looks_like_alabel, main


# ---------------------------------------------------------------------------
# _looks_like_alabel
# ---------------------------------------------------------------------------

def test_looks_like_alabel_empty_string():
    assert _looks_like_alabel("") is False


def test_looks_like_alabel_plain_domain():
    assert _looks_like_alabel("example.com") is False


def test_looks_like_alabel_simple_xn_label():
    assert _looks_like_alabel("xn--nxasmq6b") is True


def test_looks_like_alabel_case_insensitive():
    assert _looks_like_alabel("XN--nxasmq6b") is True


def test_looks_like_alabel_nested_label():
    assert _looks_like_alabel("www.xn--nxasmq6b.com") is True


def test_looks_like_alabel_prefix_only():
    assert _looks_like_alabel("xn--.com") is True


def test_looks_like_alabel_prefix_not_at_start():
    assert _looks_like_alabel("notxn--test.com") is False


# ---------------------------------------------------------------------------
# _build_parser
# ---------------------------------------------------------------------------

def test_parser_defaults():
    parser = _build_parser()
    args = parser.parse_args([])
    assert args.mode is None
    assert args.strict is False
    assert args.domain == []


def test_parser_encode_flag():
    parser = _build_parser()
    args = parser.parse_args(["-e", "example.com"])
    assert args.mode == "encode"
    assert args.domain == ["example.com"]


def test_parser_decode_flag_long_form():
    parser = _build_parser()
    args = parser.parse_args(["--decode", "example.com"])
    assert args.mode == "decode"


def test_parser_strict_flag():
    parser = _build_parser()
    args = parser.parse_args(["--strict", "example.com"])
    assert args.strict is True


def test_parser_multiple_domains():
    parser = _build_parser()
    args = parser.parse_args(["a.com", "b.com"])
    assert args.domain == ["a.com", "b.com"]


def test_parser_mutually_exclusive_encode_decode():
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["-e", "-d"])
    assert exc_info.value.code == 2


def test_parser_version(capsys):
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "idna" in captured.out


# ---------------------------------------------------------------------------
# _iter_stdin
# ---------------------------------------------------------------------------

def test_iter_stdin_strips_and_skips_blank_lines():
    stream = io.StringIO("  b\xfccher.de \n\n\txn--bcher-kva.de\t\n   \n")
    result = list(_iter_stdin(stream))
    assert result == ["b\xfccher.de", "xn--bcher-kva.de"]


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
    result = _convert_one("b\xfccher.de", "encode", True)
    assert result is True
    captured = capsys.readouterr()
    assert captured.out == "xn--bcher-kva.de\n"
    assert captured.err == ""


def test_convert_one_decode_success(capsys):
    result = _convert_one("xn--bcher-kva.de", "decode", True)
    assert result is True
    captured = capsys.readouterr()
    assert captured.out == "b\xfccher.de\n"
    assert captured.err == ""


def test_convert_one_encode_failure_label_too_long(capsys):
    domain = "a" * 64
    result = _convert_one(domain, "encode", True)
    assert result is False
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "idna: encode failed for" in captured.err
    assert repr(domain) in captured.err


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def test_main_encode_single_domain(capsys):
    ret = main(["b\xfccher.de"])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == "xn--bcher-kva.de\n"


def test_main_decode_auto_detected(capsys):
    ret = main(["xn--bcher-kva.de"])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == "b\xfccher.de\n"


def test_main_explicit_encode_flag(capsys):
    ret = main(["-e", "b\xfccher.de"])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == "xn--bcher-kva.de\n"


def test_main_mutually_exclusive_flags_exits():
    with pytest.raises(SystemExit) as exc_info:
        main(["-e", "-d", "example.com"])
    assert exc_info.value.code == 2


def test_main_single_failure_returns_one(capsys):
    domain = "a" * 64
    ret = main([domain])
    assert ret == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "idna: encode failed for" in captured.err


def test_main_mixed_success_and_failure(capsys):
    bad = "a" * 64
    ret = main(["b\xfccher.de", bad])
    assert ret == 1
    captured = capsys.readouterr()
    assert "xn--bcher-kva.de" in captured.out
    assert "idna: encode failed for" in captured.err


def test_main_reads_from_stdin_when_no_domain(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("b\xfccher.de\n"))
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == "xn--bcher-kva.de\n"


def test_main_empty_stdin_returns_zero_no_output(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_stdin_multiple_lines_decode_mode(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO("xn--bcher-kva.de\nxn--bcher-kva.de\n")
    )
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out == "b\xfccher.de\nb\xfccher.de\n"
