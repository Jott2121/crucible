import sys

import pytest

from idna import cli


def test_looks_like_alabel_detects_xn_prefix():
    # A label carrying the xn-- ACE prefix should be detected regardless of case.
    assert cli._looks_like_alabel("xn--nxasmq6b.example.com") is True
    assert cli._looks_like_alabel("XN--nxasmq6b.example.com") is True
    # Plain unicode/ascii labels without the prefix should not be detected.
    assert cli._looks_like_alabel("example.com") is False


def test_main_stdin_tty_uses_correct_error_message(monkeypatch, capsys):
    # Force stdin to look like a terminal and provide no domain arguments,
    # so argparse's error() path is triggered with the specific message.
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2

    captured = capsys.readouterr()
    expected_message = "a domain argument is required when stdin is a terminal"
    assert expected_message in captured.err
    # Guard against a mutated message that wraps the text in "XX" markers.
    assert "XX" not in captured.err
