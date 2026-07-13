import pytest
import idna.cli as cli

@pytest.mark.parametrize(('mode', 'expected_output'), [('encode', 'encoded.example'), ('decode', 'decoded.example')])
def test_convert_one_forwards_the_requested_uts46_setting(monkeypatch, capsys, mode, expected_output):
    calls = []

    def fake_encode(domain, *, uts46):
        calls.append(('encode', domain, uts46))
        return b'encoded.example'

    def fake_decode(domain, *, uts46):
        calls.append(('decode', domain, uts46))
        return 'decoded.example'
    monkeypatch.setattr(cli, 'encode', fake_encode)
    monkeypatch.setattr(cli, 'decode', fake_decode)
    assert cli._convert_one('input.example', mode, False) is True
    assert capsys.readouterr().out == expected_output + '\n'
    assert calls == [(mode, 'input.example', False)]

@pytest.mark.parametrize(('argv', 'expected_uts46'), [(['example.com'], True), (['--strict', 'example.com'], False)])
def test_main_uses_documented_uts46_default_and_strict_override(monkeypatch, argv, expected_uts46):
    calls = []

    def fake_convert(domain, mode, uts46):
        calls.append((domain, mode, uts46))
        return True
    monkeypatch.setattr(cli, '_convert_one', fake_convert)
    assert cli.main(argv) == 0
    assert calls == [('example.com', 'encode', expected_uts46)]

def test_main_reports_a_clear_error_when_terminal_stdin_has_no_domain(monkeypatch, capsys):

    class TerminalStdin:

        def isatty(self):
            return True
    monkeypatch.setattr(cli.sys, 'stdin', TerminalStdin())
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2
    assert 'a domain argument is required when stdin is a terminal' in capsys.readouterr().err
