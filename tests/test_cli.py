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


def test_cmd_run_derives_scope_from_detect_and_passes_it_to_subjectenv(monkeypatch, tmp_path):
    """`crucible harden`/`oneshot` must build SubjectEnv's scope= the SAME way
    `crucible scope` does (scope.detect), not leave it None -- otherwise
    harden's preflight rewrites [tool.mutmut] to a bare source_paths and
    silently discards also_copy/pytest_args/the src-shim that scope's canary
    already validated. Spy on SubjectEnv to capture exactly the scope kwarg
    it receives; stop the run immediately after construction (no real
    provider/mutmut work needed for this assertion)."""
    from crucible import cli
    import crucible.scope as scope_mod

    captured = {}

    class _StopEarly(Exception):
        pass

    class SpySubjectEnv:
        def __init__(self, *args, **kwargs):
            captured["scope"] = kwargs.get("scope")
            raise _StopEarly("stop-before-any-real-work")

    monkeypatch.setattr(
        scope_mod, "detect",
        lambda s, m: scope_mod.ScopePlan(
            module=m, also_copy=["pkga", "pkgb"], pytest_args=["--ignore=tests/test_hazard.py"],
            needs_src_shim=True, notes=[],
        ),
    )
    monkeypatch.setattr(cli, "SubjectEnv", SpySubjectEnv)

    import pytest
    with pytest.raises(_StopEarly):
        cli.main(["harden", str(tmp_path), "--module", "pkga/mod.py",
                  "--tester", "fake", "--critic", "fake"])

    assert captured["scope"] == {
        "also_copy": ["pkga", "pkgb"],
        "pytest_args": ["--ignore=tests/test_hazard.py"],
        "extra_files": {"conftest.py": scope_mod.SRC_SHIM},
    }


def test_cmd_run_scope_omits_extra_files_and_uses_none_pytest_args_when_plan_is_plain(
    monkeypatch, tmp_path,
):
    """The counterpart shape: no src-shim needed and no pytest_args -- the
    scope dict must carry pytest_args=None (not []) and no extra_files key,
    matching env.py preflight's `self.scope.get("pytest_args")` /
    `.get("extra_files") or {}` handling."""
    from crucible import cli
    import crucible.scope as scope_mod

    captured = {}

    class _StopEarly(Exception):
        pass

    class SpySubjectEnv:
        def __init__(self, *args, **kwargs):
            captured["scope"] = kwargs.get("scope")
            raise _StopEarly("stop-before-any-real-work")

    monkeypatch.setattr(
        scope_mod, "detect",
        lambda s, m: scope_mod.ScopePlan(
            module=m, also_copy=["pkga"], pytest_args=[], needs_src_shim=False, notes=[],
        ),
    )
    monkeypatch.setattr(cli, "SubjectEnv", SpySubjectEnv)

    import pytest
    with pytest.raises(_StopEarly):
        cli.main(["oneshot", str(tmp_path), "--module", "pkga/mod.py",
                  "--tester", "fake", "--critic", "fake"])

    assert captured["scope"] == {"also_copy": ["pkga"], "pytest_args": None}


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
