import pytest
import idna.cli as cli


# ---------------------------------------------------------------------------
# _convert_one: uts46 must be forwarded exactly as given to encode()/decode()
# ---------------------------------------------------------------------------

def test_convert_one_encode_passes_exact_uts46(monkeypatch, capsys):
    calls = []

    def fake_encode(domain, uts46=False):
        calls.append(uts46)
        return b"xn--result"

    monkeypatch.setattr(cli, "encode", fake_encode)
    ok = cli._convert_one("example.com", "encode", True)
    assert ok is True
    assert calls == [True]
    out = capsys.readouterr().out.strip()
    assert out == "xn--result"


def test_convert_one_decode_passes_exact_uts46(monkeypatch, capsys):
    calls = []

    def fake_decode(domain, uts46=False):
        calls.append(uts46)
        return "unicode-result"

    monkeypatch.setattr(cli, "decode", fake_decode)
    ok = cli._convert_one("xn--example", "decode", True)
    assert ok is True
    assert calls == [True]
    out = capsys.readouterr().out.strip()
    assert out == "unicode-result"


def test_convert_one_encode_uses_lowercase_ascii_decode(monkeypatch, capsys):
    class FakeBytes:
        def decode(self, encoding):
            # This must be the exact lowercase "ascii" codec name.
            assert encoding == "ascii"
            return "strict-ascii-result"

    def fake_encode(domain, uts46=False):
        return FakeBytes()

    monkeypatch.setattr(cli, "encode", fake_encode)
    ok = cli._convert_one("example.com", "encode", True)
    assert ok is True
    out = capsys.readouterr().out.strip()
    assert out == "strict-ascii-result"


# ---------------------------------------------------------------------------
# _looks_like_alabel: must decode the ACE prefix using lowercase "ascii"
# ---------------------------------------------------------------------------

def test_looks_like_alabel_uses_lowercase_ascii(monkeypatch):
    class FakePrefix:
        def decode(self, encoding):
            assert encoding == "ascii"
            return "xn--"

    monkeypatch.setattr(cli, "_alabel_prefix", FakePrefix())
    assert cli._looks_like_alabel("xn--abc.com") is True
    assert cli._looks_like_alabel("abc.com") is False


# ---------------------------------------------------------------------------
# main(): uts46 must be computed as `not args.strict`
# ---------------------------------------------------------------------------

def test_main_uts46_computation_no_strict(monkeypatch):
    calls = []

    def fake_convert_one(domain, mode, uts46):
        calls.append(uts46)
        return True

    monkeypatch.setattr(cli, "_convert_one", fake_convert_one)
    result = cli.main(["example.com"])
    assert result == 0
    assert calls == [True]
    assert calls[0] is True


def test_main_uts46_computation_strict(monkeypatch):
    calls = []

    def fake_convert_one(domain, mode, uts46):
        calls.append(uts46)
        return True

    monkeypatch.setattr(cli, "_convert_one", fake_convert_one)
    result = cli.main(["--strict", "example.com"])
    assert result == 0
    assert calls == [False]
    assert calls[0] is False


# ---------------------------------------------------------------------------
# main(): error message when stdin is a terminal and no domain is given
# ---------------------------------------------------------------------------

def test_main_stdin_terminal_error_message(monkeypatch, capsys):
    class FakeStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", FakeStdin())
    with pytest.raises(SystemExit):
        cli.main([])
    captured = capsys.readouterr()
    assert "a domain argument is required when stdin is a terminal" in captured.err
    assert "XX" not in captured.err
