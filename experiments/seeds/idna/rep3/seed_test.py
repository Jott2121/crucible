"""Tests for idna.cli."""
import io
import sys
import pytest
from idna.cli import _build_parser, _iter_stdin, _looks_like_alabel, main
from idna.package_data import __version__

def test_looks_like_alabel_plain_ascii():
    assert _looks_like_alabel('example.com') is False

def test_looks_like_alabel_with_prefix():
    assert _looks_like_alabel('xn--nxasmq6b') is True

def test_looks_like_alabel_with_prefix_in_subdomain():
    assert _looks_like_alabel('www.xn--nxasmq6b.com') is True

def test_looks_like_alabel_case_insensitive():
    assert _looks_like_alabel('XN--nxasmq6b') is True

def test_looks_like_alabel_empty_string():
    assert _looks_like_alabel('') is False

def test_looks_like_alabel_no_dots_no_prefix():
    assert _looks_like_alabel('a.b.c') is False

def test_parser_prog_name():
    parser = _build_parser()
    assert parser.prog == 'python -m idna'

def test_parser_defaults():
    parser = _build_parser()
    args = parser.parse_args([])
    assert args.domain == []
    assert args.mode is None
    assert args.strict is False

def test_parser_encode_flag_short():
    parser = _build_parser()
    args = parser.parse_args(['-e', 'foo.com'])
    assert args.mode == 'encode'
    assert args.domain == ['foo.com']

def test_parser_decode_flag_long():
    parser = _build_parser()
    args = parser.parse_args(['--decode', 'foo.com', 'bar.com'])
    assert args.mode == 'decode'
    assert args.domain == ['foo.com', 'bar.com']

def test_parser_strict_flag():
    parser = _build_parser()
    args = parser.parse_args(['--strict'])
    assert args.strict is True

def test_parser_mutually_exclusive_encode_decode():
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(['-e', '-d'])
    assert exc.value.code == 2

def test_parser_version(capsys):
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(['--version'])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f'idna {__version__}'

def test_iter_stdin_strips_and_skips_blanks():
    stream = io.StringIO('first.com\n\n  second.com  \n   \nthird.com')
    result = list(_iter_stdin(stream))
    assert result == ['first.com', 'second.com', 'third.com']

def test_iter_stdin_empty_stream():
    assert list(_iter_stdin(io.StringIO(''))) == []

def test_iter_stdin_only_blank_lines():
    assert list(_iter_stdin(io.StringIO('\n\n   \n\t\n'))) == []

def test_main_encode_default(capsys):
    code = main(['München.de'])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == 'xn--mnchen-3ya.de\n'

def test_main_decode_default(capsys):
    code = main(['xn--mnchen-3ya.de'])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == 'münchen.de\n'

def test_main_explicit_encode_flag(capsys):
    code = main(['-e', 'example.com'])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == 'example.com\n'

def test_main_strict_ascii_domain_unaffected(capsys):
    code = main(['--strict', 'example.com'])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == 'example.com\n'

def test_main_encode_failure_label_too_long(capsys):
    long_label = 'a' * 64
    domain = f'{long_label}.com'
    code = main([domain])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ''
    assert f'idna: encode failed for {domain!r}' in captured.err

def test_main_multiple_domains_first_ok_second_fails(capsys):
    long_label = 'b' * 64
    bad_domain = f'{long_label}.org'
    code = main(['example.com', bad_domain])
    captured = capsys.readouterr()
    assert code == 1
    assert 'example.com' in captured.out
    assert f'idna: encode failed for {bad_domain!r}' in captured.err

def test_main_stdin_piped_multiple_domains(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'stdin', io.StringIO('example.com\n\nfoo.org\n'))
    code = main([])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == 'example.com\nfoo.org\n'

def test_main_stdin_piped_empty_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'stdin', io.StringIO('\n\n   \n'))
    code = main([])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ''

def test_main_stdin_tty_raises_system_exit(monkeypatch):

    class _FakeTTYStdin:

        def isatty(self):
            return True
    monkeypatch.setattr(sys, 'stdin', _FakeTTYStdin())
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
