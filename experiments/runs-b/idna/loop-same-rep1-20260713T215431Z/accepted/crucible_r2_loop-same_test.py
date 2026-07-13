import sys
import pytest

from idna import cli


def test_convert_one_encode_uses_lowercase_ascii_decode(capsys):
    # "münchen" encodes to the well-known A-label "xn--mnchen-3ya".
    ok = cli._convert_one("münchen", "encode", True)
    captured = capsys.readouterr()
    assert ok is True
    assert captured.out.strip() == "xn--mnchen-3ya"


def test_convert_one_decode_roundtrip(capsys):
    ok = cli._convert_one("xn--mnchen-3ya", "decode", True)
    captured = capsys.readouterr()
    assert ok is True
    assert captured.out.strip() == "münchen"


def test_looks_like_alabel_detects_prefix():
    assert cli._looks_like_alabel("xn--mnchen-3ya.de") is True
    assert cli._looks_like_alabel("XN--mnchen-3ya.de") is True
    assert cli._looks_like_alabel("example.com") is False


def test_main_error_message_when_stdin_is_terminal(monkeypatch, capsys):
    class FakeStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", FakeStdin())

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2

    captured = capsys.readouterr()
    expected_message = "a domain argument is required when stdin is a terminal"
    assert expected_message in captured.err
    assert "XX" not in captured.err
