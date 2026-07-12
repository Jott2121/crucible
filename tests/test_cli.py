"""Fast, monkeypatch-based tests for the `crucible scope` CLI subcommand."""
import json


def test_cli_report_line_includes_billing(tmp_path, capsys):
    """Spec §4 'never silently mix': the report line must carry the run's
    billing field (summarize already computes it -- api / max-plan /
    mixed:...), so a Max-plan shadow-priced run can never be read as metered
    spend. Real minimal run dir, no monkeypatching."""
    from crucible import cli

    run_dir = tmp_path / "20260711T000000Z-subject-harden"
    run_dir.mkdir()
    (run_dir / "meta.json").write_text(json.dumps({
        "arm": "harden", "tester_billing": "max-plan", "critic_billing": "max-plan",
    }))
    (run_dir / "receipt.jsonl").write_text(json.dumps({
        "round": 0, "role": "tester", "status": "ok",
        "kills": ["m1"], "survivors_before": ["m1", "m2"], "survivors_after": ["m2"],
    }) + "\n")
    (run_dir / "result.json").write_text(json.dumps({
        "verdict": "dry", "total_cost_usd": 0.5,
    }))
    rc = cli.main(["report", str(run_dir)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "billing=max-plan" in out
    assert "lean=ambient" in out


def test_cli_scope_missing_module_refuses_exit_4_no_traceback(tmp_path, capsys):
    """scope.detect raises FileNotFoundError for a missing module; the scope
    branch must route it through the same REFUSING/exit-4 path as RuntimeError
    instead of leaking a raw traceback."""
    from crucible import cli

    rc = cli.main(["scope", str(tmp_path), "--module", "nope/missing.py"])
    out = capsys.readouterr().out
    assert rc == 4
    assert "REFUSING:" in out
    assert "nope/missing.py" in out


def test_cli_harden_missing_module_clean_error_nonzero_exit(tmp_path, capsys):
    """harden/oneshot derive their scope via scope.detect (fix B); a missing
    module must produce a clean one-line error naming the module and a
    nonzero exit -- never an uncaught FileNotFoundError traceback."""
    from crucible import cli

    rc = cli.main(["harden", str(tmp_path), "--module", "nope/missing.py",
                   "--tester", "fake", "--critic", "fake"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "nope/missing.py" in out
    assert "Traceback" not in out


def test_cli_harden_refuses_runs_dir_inside_subject(tmp_path, capsys):
    """Gate-7 live defect 1: a runs-dir inside the subject repo makes
    crucible's own receipt writes (meta.json et al.) trip its own add-only
    guardrail mid-run ('?? .crucible-runs/...meta.json'). _cmd_run must
    refuse fail-loud BEFORE preflight or any model call: clean error naming
    the failure, nonzero exit. Proof no work started: the subject is not
    even a git repo (preflight would raise) and the fake provider has no
    replies (any model call would raise) -- a clean rc-2 return means
    neither was reached."""
    from crucible import cli

    (tmp_path / "mypkg").mkdir()
    (tmp_path / "mypkg" / "mod.py").write_text("X = 1\n")
    rc = cli.main(["harden", str(tmp_path), "--module", "mypkg/mod.py",
                   "--tester", "fake", "--critic", "fake",
                   "--runs-dir", str(tmp_path / ".crucible-runs")])
    out = capsys.readouterr().out
    assert rc == 2
    assert "runs-dir" in out
    assert "inside the subject" in out
    assert "Traceback" not in out


def test_cli_scope_help_states_honest_limitation(capsys):
    """Spec §6: the honest limitation ('heuristics target well-formed Python
    repos with pytest; a repo the gate cannot validate is refused, not
    guessed') must be stated in the scope subcommand's --help text."""
    import pytest

    from crucible import cli

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["scope", "--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "well-formed Python repos with pytest" in out
    assert "refused, not guessed" in out


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
