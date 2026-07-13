import pytest
from idna.cli import _looks_like_alabel


def test_looks_like_alabel_detects_xn_prefix():
    assert _looks_like_alabel("xn--nxasmq6b.com") is True


def test_looks_like_alabel_detects_uppercase_xn_prefix():
    assert _looks_like_alabel("XN--nxasmq6b.com") is True


def test_looks_like_alabel_mixed_case_prefix():
    assert _looks_like_alabel("Xn--nxasmq6b.com") is True


def test_looks_like_alabel_false_for_plain_domain():
    assert _looks_like_alabel("example.com") is False


def test_looks_like_alabel_detects_prefix_in_second_label():
    assert _looks_like_alabel("www.xn--nxasmq6b.com") is True


def test_looks_like_alabel_unicode_dots():
    # Using a fullwidth dot (U+FF0E) which the unicode dots regex should split on
    assert _looks_like_alabel("www\uff0exn--nxasmq6b\uff0ecom") is True
