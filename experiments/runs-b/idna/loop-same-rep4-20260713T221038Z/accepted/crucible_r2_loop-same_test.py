import sys
import types
import pytest

from idna.cli import _looks_like_alabel, main


def test_looks_like_alabel_detects_ace_prefix_case_insensitive():
    # Uses ascii codec explicitly; must correctly detect xn-- prefix
    # regardless of the label's case.
    assert _looks_like_alabel("xn--nxasmq6b.example") is True
    assert _looks_like_alabel("XN--nxasmq6b.example") is True
    assert _looks_like_alabel("example.com") is False


def test_looks_like_alabel_multi_label_with_unicode_dots():
    # full-width dot separator, second label carries the xn-- prefix
    s = "example\u3002xn--nxasmq6b"
    assert _looks_like_alabel(s) is True


def test_main_stdin_terminal_error_message(monkeypatch, capsys):
    # Simulate no domain arguments and stdin being a terminal (tty).
    fake_stdin = types.SimpleNamespace(isatty=lambda: True)
    monkeypatch.setattr(sys, "stdin", fake_stdin)

    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "a domain argument is required when stdin is a terminal" in captured.err
