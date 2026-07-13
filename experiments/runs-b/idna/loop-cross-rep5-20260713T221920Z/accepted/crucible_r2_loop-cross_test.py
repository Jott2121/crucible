import io
import sys

import pytest

from idna import cli


class TerminalInput(io.StringIO):
    def isatty(self):
        return True


def test_main_reports_original_missing_domain_error_for_terminal_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", TerminalInput())

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2
    assert (
        "python -m idna: error: a domain argument is required when stdin is a terminal"
        in capsys.readouterr().err
    )
