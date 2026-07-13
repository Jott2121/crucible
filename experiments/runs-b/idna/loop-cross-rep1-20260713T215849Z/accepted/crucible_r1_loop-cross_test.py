import sys
import pytest
import idna.cli as cli

def test_looks_like_alabel_decodes_the_ace_prefix_as_ascii(monkeypatch):

    class Prefix:

        def decode(self, encoding):
            if encoding == 'ascii':
                return 'xn--'
            return 'not-the-ace-prefix'
    monkeypatch.setattr(cli, '_alabel_prefix', Prefix())
    assert cli._looks_like_alabel('www.XN--BCHER-KVA.example') is True

def test_convert_one_encode_passes_uts46_and_uses_ascii_output_codec(monkeypatch, capsys):
    calls = []

    class EncodedResult:

        def decode(self, encoding):
            calls.append(('decode', encoding))
            return 'expected-ascii-domain'

    def fake_encode(domain, *, uts46):
        calls.append(('encode', domain, uts46))
        return EncodedResult()
    monkeypatch.setattr(cli, 'encode', fake_encode)
    assert cli._convert_one('unicode.example', 'encode', True) is True
    assert capsys.readouterr().out == 'expected-ascii-domain\n'
    assert calls == [('encode', 'unicode.example', True), ('decode', 'ascii')]

def test_convert_one_decode_passes_uts46(monkeypatch, capsys):
    calls = []

    def fake_decode(domain, *, uts46):
        calls.append((domain, uts46))
        return 'decoded.example'
    monkeypatch.setattr(cli, 'decode', fake_decode)
    assert cli._convert_one('xn--example', 'decode', False) is True
    assert capsys.readouterr().out == 'decoded.example\n'
    assert calls == [('xn--example', False)]

def test_main_defaults_to_uts46_and_strict_disables_it(monkeypatch):
    received = []

    def fake_convert(domain, mode, uts46):
        received.append((domain, mode, uts46))
        return True
    monkeypatch.setattr(cli, '_convert_one', fake_convert)
    assert cli.main(['ＦＯＯ.example']) == 0
    assert received == [('ＦＯＯ.example', 'encode', True)]
    received.clear()
    assert cli.main(['--strict', 'ＦＯＯ.example']) == 0
    assert received == [('ＦＯＯ.example', 'encode', False)]

def test_main_reports_documented_error_when_stdin_is_terminal(monkeypatch, capsys):

    class TerminalStdin:

        def isatty(self):
            return True
    monkeypatch.setattr(sys, 'stdin', TerminalStdin())
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])
    assert exc_info.value.code == 2
    assert 'a domain argument is required when stdin is a terminal' in capsys.readouterr().err
