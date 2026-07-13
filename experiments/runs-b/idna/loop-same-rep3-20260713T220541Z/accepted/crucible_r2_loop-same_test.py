import sys
import pytest
from idna.cli import main, _looks_like_alabel, _convert_one


def test_main_errors_with_exact_message_when_stdin_is_terminal(monkeypatch, capsys):
    # Force stdin to look like a terminal so no domain args triggers parser.error
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    # Exact wording must be preserved (no stray "XX" markers from a broken mutant)
    assert "a domain argument is required when stdin is a terminal" in captured.err
    assert "XX" not in captured.err


def test_looks_like_alabel_detects_ace_prefix_correctly():
    assert _looks_like_alabel("xn--mnchen-3ya.de") is True
    assert _looks_like_alabel("münchen.de") is False
    assert _looks_like_alabel("example.com") is False


def test_convert_one_encode_writes_expected_ascii_string(capsys):
    result = _convert_one("münchen.de", "encode", True)
    captured = capsys.readouterr()
    assert result is True
    assert captured.out.strip() == "xn--mnchen-3ya.de"


def test_convert_one_decode_writes_expected_unicode_string(capsys):
    result = _convert_one("xn--mnchen-3ya.de", "decode", True)
    captured = capsys.readouterr()
    assert result is True
    assert captured.out.strip() == "münchen.de"
