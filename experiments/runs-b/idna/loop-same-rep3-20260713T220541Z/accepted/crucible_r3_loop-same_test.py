import pytest
from idna import encode, decode
from idna.cli import _convert_one, _looks_like_alabel


def test_convert_one_encode_output_matches_manual_ascii_decode(capsys):
    """_convert_one in encode mode must print exactly what encode(...).decode
    produces as an ASCII string (the mutant swaps the codec name casing,
    which should still produce the same textual output)."""
    domain = "münchen"
    ok = _convert_one(domain, "encode", True)
    assert ok is True
    captured = capsys.readouterr()
    expected = encode(domain, uts46=True).decode("ascii")
    assert captured.out.strip() == expected
    # Sanity check on the independently computed expected value.
    assert expected == "xn--mnchen-3ya"


def test_convert_one_decode_output_matches_decode_function(capsys):
    domain = "xn--mnchen-3ya"
    ok = _convert_one(domain, "decode", True)
    assert ok is True
    captured = capsys.readouterr()
    expected = decode(domain, uts46=True)
    assert captured.out.strip() == expected
    assert expected == "münchen"


def test_looks_like_alabel_detects_uppercase_prefix():
    # The xn-- prefix check must be case-insensitive, matching against the
    # lowercase "xn--" prefix regardless of the source string's casing.
    assert _looks_like_alabel("XN--nxasmq6b") is True


def test_looks_like_alabel_false_for_plain_unicode():
    assert _looks_like_alabel("münchen") is False


def test_looks_like_alabel_multi_label_detection():
    assert _looks_like_alabel("www.xn--nxasmq6b.com") is True


def test_looks_like_alabel_false_for_plain_ascii_domain():
    assert _looks_like_alabel("example.com") is False
