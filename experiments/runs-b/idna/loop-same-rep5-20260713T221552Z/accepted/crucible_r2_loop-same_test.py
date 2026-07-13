import sys
import pytest

from idna.cli import main


class _FakeTTYStdin:
    """A stand-in for sys.stdin that reports isatty() == True and yields no lines."""

    def isatty(self) -> bool:
        return True

    def __iter__(self):
        return iter([])


def test_error_message_exact_when_no_domain_and_tty(monkeypatch, capsys):
    """When no domain args are given and stdin looks like a terminal, main()
    should call parser.error with the exact original message text.
    Mutants that pass None, wrap the text in 'XX', or upper-case it must fail
    this exact-match check.
    """
    monkeypatch.setattr(sys, "stdin", _FakeTTYStdin())

    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code == 2

    captured = capsys.readouterr()
    lines = [line for line in captured.err.splitlines() if line]
    assert lines, "expected some stderr output from parser.error"

    expected_message = "a domain argument is required when stdin is a terminal"
    expected_line = f"python -m idna: error: {expected_message}"

    # The exact final line must match the original message precisely.
    assert lines[-1] == expected_line


def test_convert_one_encode_output_is_correct_ascii(capsys):
    """Sanity check that encode/decode path prints the correct ASCII label."""
    from idna.cli import _convert_one

    ok = _convert_one("café.example", "encode", True)
    assert ok is True

    captured = capsys.readouterr()
    # Independently known correct A-label encoding of café.example
    assert captured.out.strip() == "xn--caf-dma.example"


def test_looks_like_alabel_detects_ace_prefix():
    from idna.cli import _looks_like_alabel

    assert _looks_like_alabel("xn--caf-dma.example") is True
    assert _looks_like_alabel("cafe.example") is False
