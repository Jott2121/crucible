"""Fast, monkeypatch-based tests for the `crucible scope` CLI subcommand."""


def test_cli_scope_subcommand(monkeypatch, tmp_path, capsys):
    from crucible import cli
    import crucible.scope as scope_mod
    calls = {}
    monkeypatch.setattr(scope_mod, "detect",
                        lambda s, m: scope_mod.ScopePlan(m, ["mypkg"], [], False, []))
    monkeypatch.setattr(scope_mod, "apply", lambda s, p: calls.setdefault("applied", p))
    monkeypatch.setattr(scope_mod, "canary_probe",
                        lambda s, m, run=None: scope_mod.CanaryVerdict(3, 5, 10, True))
    (tmp_path / "mypkg").mkdir(parents=True)
    (tmp_path / "mypkg" / "mod.py").write_text("X = 1\n")
    rc = cli.main(["scope", str(tmp_path), "--module", "mypkg/mod.py"])
    out = capsys.readouterr().out
    assert rc == 0 and "canary" in out.lower() and "3 -> 5" in out


def test_cli_scope_subcommand_canary_failure_exits_4(monkeypatch, tmp_path):
    from crucible import cli
    import crucible.scope as scope_mod
    monkeypatch.setattr(scope_mod, "detect",
                        lambda s, m: scope_mod.ScopePlan(m, ["mypkg"], [], False, []))
    monkeypatch.setattr(scope_mod, "apply", lambda s, p: None)
    monkeypatch.setattr(scope_mod, "canary_probe",
                        lambda s, m, run=None: scope_mod.CanaryVerdict(3, 3, 10, False))
    (tmp_path / "mypkg").mkdir(parents=True)
    (tmp_path / "mypkg" / "mod.py").write_text("X = 1\n")
    rc = cli.main(["scope", str(tmp_path), "--module", "mypkg/mod.py"])
    assert rc == 4


def test_cli_scope_subcommand_waived_exits_0(monkeypatch, tmp_path, capsys):
    """Two-branch canary policy (2026-07-11, owner-approved): the existing
    suite already kills under this scope -- WAIVED, exit 0, distinct line."""
    from crucible import cli
    import crucible.scope as scope_mod
    monkeypatch.setattr(scope_mod, "detect",
                        lambda s, m: scope_mod.ScopePlan(m, ["mypkg"], [], False, []))
    monkeypatch.setattr(scope_mod, "apply", lambda s, p: None)
    monkeypatch.setattr(scope_mod, "canary_probe",
                        lambda s, m, run=None: scope_mod.CanaryVerdict(3, 3, 10, True, waived=True))
    (tmp_path / "mypkg").mkdir(parents=True)
    (tmp_path / "mypkg" / "mod.py").write_text("X = 1\n")
    rc = cli.main(["scope", str(tmp_path), "--module", "mypkg/mod.py"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WAIVED" in out
    assert "3 of 10 mutants" in out
    assert "collection proven" in out.lower()


def test_cli_scope_subcommand_runtimeerror_exits_4_no_traceback(monkeypatch, tmp_path, capsys):
    """A RuntimeError anywhere in detect/apply/canary_probe is a single refusal
    path: plain "REFUSING: {exc}" line, exit 4, no traceback leaked to exit 1."""
    from crucible import cli
    import crucible.scope as scope_mod
    monkeypatch.setattr(scope_mod, "detect",
                        lambda s, m: scope_mod.ScopePlan(m, ["mypkg"], [], False, []))
    monkeypatch.setattr(scope_mod, "apply", lambda s, p: None)

    def boom(s, m, run=None):
        raise RuntimeError("canary failed on pristine code -- the probe is wrong, not the subject")

    monkeypatch.setattr(scope_mod, "canary_probe", boom)
    (tmp_path / "mypkg").mkdir(parents=True)
    (tmp_path / "mypkg" / "mod.py").write_text("X = 1\n")
    rc = cli.main(["scope", str(tmp_path), "--module", "mypkg/mod.py"])
    out = capsys.readouterr().out
    assert rc == 4
    assert "REFUSING: canary failed on pristine" in out
