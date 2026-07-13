import pytest
import idna
from idna.cli import _looks_like_alabel, _convert_one


def test_looks_like_alabel_true_for_alabel_domain():
    assert _looks_like_alabel("xn--nxasmq6b.com") is True


def test_looks_like_alabel_true_case_insensitive():
    # Prefix matching must be case-insensitive: "XN--" should still match.
    assert _looks_like_alabel("XN--nxasmq6b.com") is True


def test_looks_like_alabel_false_for_plain_domain():
    assert _looks_like_alabel("example.com") is False


def test_looks_like_alabel_true_for_second_label():
    assert _looks_like_alabel("foo.xn--nxasmq6b") is True


def test_convert_one_encode_writes_expected_ascii_result(capsys):
    domain = "münchen.de"
    expected = idna.encode(domain, uts46=True).decode("ascii")

    ok = _convert_one(domain, "encode", True)
    captured = capsys.readouterr()

    assert ok is True
    assert captured.out.strip() == expected


def test_convert_one_decode_writes_expected_unicode_result(capsys):
    domain = idna.encode("münchen.de", uts46=True).decode("ascii")
    expected = idna.decode(domain, uts46=True)

    ok = _convert_one(domain, "decode", True)
    captured = capsys.readouterr()

    assert ok is True
    assert captured.out.strip() == expected


def test_convert_one_encode_failure_reports_error(capsys):
    # An overly long label should fail IDNA encoding.
    bad_domain = "a" * 64
    ok = _convert_one(bad_domain, "encode", True)
    captured = capsys.readouterr()

    assert ok is False
    assert captured.err.strip() != ""
    assert "encode failed" in captured.err
