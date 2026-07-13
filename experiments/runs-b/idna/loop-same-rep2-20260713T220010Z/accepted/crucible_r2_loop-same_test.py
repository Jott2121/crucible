import sys
import pytest

from idna.cli import _convert_one, _looks_like_alabel, main


def test_convert_one_encode_produces_expected_ascii_label(capsys):
    """Known IDNA UTS#46 encoding for 'münchen.de' is 'xn--mnchen-3ya.de'."""
    ok = _convert_one("münchen.de", "encode", True)
    captured = capsys.readouterr()
    assert ok is True
    assert captured.out.strip() == "xn--mnchen-3ya.de"


def test_looks_like_alabel_detects_mixed_case_prefix():
    # Mixed-case xn-- prefix should still be recognized as an A-label.
    assert _looks_like_alabel("XN--nxasmq6b.example") is True
    assert _looks_like_alabel("xn--nxasmq6b.example") is True
    assert _looks_like_alabel("example.com") is False


def test_main_errors_with_exact_message_when_stdin_is_tty(monkeypatch, capsys):
    # Force the "no domain given, stdin is a terminal" branch.
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "a domain argument is required when stdin is a terminal" in captured.err
