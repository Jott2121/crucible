import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from crucible.scope import ScopePlan, apply, detect

SHIM = 'import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))\n'


def _clone_subject(tmp_path, strip_tests=False):
    """Copy tests/fixtures/subject to a fresh tmp_path, optionally stripping
    its tests/ dir entirely (used to build a subject where NO existing test
    touches the scoped module at all -- the true zero-coverage case, distinct
    from merely zero-KILLS), git-init/commit it, and pip install -e it into
    this venv."""
    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    if strip_tests:
        shutil.rmtree(subject / "tests")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(subject)], check=True)
    return subject


@pytest.fixture
def subject_clone(tmp_path):
    """Committed git clone of tests/fixtures/subject, installed editable into
    this venv -- mirrors the inline-clone pattern in tests/test_cli_e2e.py
    (no shared `subject_clone` fixture exists elsewhere in the repo; this is
    the first one, scoped locally to this test module)."""
    return _clone_subject(tmp_path)


def _mk(tmp_path, files):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return tmp_path


def test_detect_package_dir_layout(tmp_path):
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n", "tests/test_mod.py": "import mypkg\n"})
    plan = detect(repo, "mypkg/mod.py")
    assert plan.also_copy == ["mypkg"]
    assert plan.needs_src_shim is False
    assert plan.pytest_args == []


def test_detect_src_layout_needs_shim(tmp_path):
    repo = _mk(tmp_path, {"src/mod.py": "X = 1\n"})
    plan = detect(repo, "src/mod.py")
    assert plan.also_copy == ["src"]
    assert plan.needs_src_shim is True


def test_detect_flags_sandbox_hazard_test_files(tmp_path):
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "tests/test_ok.py": "import mypkg\n",
        "tests/test_hazard.py": "from toolbelt import helper\n",  # local pkg outside also_copy
        "toolbelt/__init__.py": "helper = 1\n",
    })
    plan = detect(repo, "mypkg/mod.py")
    assert plan.pytest_args == ["--ignore=tests/test_hazard.py"]


def test_detect_missing_module_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        detect(tmp_path, "nope/missing.py")


def test_apply_writes_scope_and_shim(tmp_path):
    repo = _mk(tmp_path, {"src/mod.py": "X = 1\n"})
    apply(repo, detect(repo, "src/mod.py"))
    py = (repo / "pyproject.toml").read_text()
    assert 'source_paths = ["src/mod.py"]' in py
    assert 'also_copy = ["src"]' in py
    assert (repo / "conftest.py").read_text() == SHIM


def test_canary_probe_passes_when_kills_increase(tmp_path, monkeypatch):
    """killed=0 baseline (empty/weak suite) -- exercises the STRICT branch:
    write canary, pristine-check, measure again, require a strict increase."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, killed):
            self.counts = {"killed": killed}
            self.all_mutants = 10
            self.survivors = []

    measures = iter([FakeOutcome(0), FakeOutcome(2)])

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return next(measures)

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n", "tests/__init__.py": ""})

    # pristine canary check subprocess: exit 0
    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        class P:
            returncode, stdout, stderr = 0, "1 passed", ""
        return P()

    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)
    assert v.passed is True and (v.kills_before, v.kills_after) == (0, 2)
    assert v.waived is False
    assert not (repo / "tests" / "crucible_canary_test.py").exists()  # cleaned up


def test_canary_probe_fails_when_kills_flat(tmp_path, monkeypatch):
    """killed=0 baseline, still 0 after -- STRICT branch, no increase -> refused."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, killed):
            self.counts = {"killed": killed}
            self.all_mutants = 10
            self.survivors = []

    measures = iter([FakeOutcome(0), FakeOutcome(0)])

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return next(measures)

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        class P:
            returncode, stdout, stderr = 0, "1 passed", ""
        return P()

    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)
    assert v.passed is False
    assert v.waived is False


def _waived_setup(monkeypatch, tmp_path, extra_files):
    """Shared rig for the waived-branch discovery-config tests: a fake engine
    whose baseline already kills (killed=3, so canary_probe reaches the WAIVED
    branch), a `run` stub that raises if any subprocess is ever attempted
    (the config scan must be pure file reading), and a repo built from
    `extra_files` on top of the minimal module."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        counts = {"killed": 3}
        all_mutants = 10
        survivors = []

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return FakeOutcome()

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n", **extra_files})

    def fail_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        raise AssertionError("canary_probe must not shell out in the waived branch")

    return scope_mod, repo, fail_run


def test_waiver_refused_when_python_files_cannot_match_fresh_tests(tmp_path, monkeypatch):
    """python_files that no crucible_*_test.py name can ever match -- the v6
    failure class through the side door: the existing suite kills (waiver
    would be granted) while fresh generated files would never be collected.
    Refuse before waiving."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pyproject.toml": '[tool.pytest.ini_options]\npython_files = ["check_*.py"]\n',
    })
    with pytest.raises(RuntimeError, match=r"python_files in pyproject\.toml"):
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)


def test_waiver_ok_when_python_files_matches_test_suffix(tmp_path, monkeypatch):
    """python_files that includes *_test.py -- a fresh crucible_x_test.py IS
    collectable, so the waiver proceeds."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pyproject.toml":
            '[tool.pytest.ini_options]\npython_files = ["test_*.py", "*_test.py"]\n',
    })
    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert v.passed is True and v.waived is True


def test_waiver_refused_when_testpaths_excludes_tests_dir(tmp_path, monkeypatch):
    """testpaths pinned to dirs NOT including tests/ -> refuse: crucible
    writes generated files to tests/crucible_*_test.py (env._known_generated),
    outside every pinned path, so they would never be collected."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pyproject.toml": '[tool.pytest.ini_options]\ntestpaths = ["spec"]\n',
    })
    with pytest.raises(RuntimeError, match=r"testpaths in pyproject\.toml"):
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)


def test_waiver_ok_when_testpaths_includes_tests_dir(tmp_path, monkeypatch):
    """testpaths = ["tests"] (the common idiom -- rag-guard's exact config) is
    provably safe: crucible writes fresh files to tests/crucible_*_test.py,
    INSIDE the pinned path. A blanket testpaths refusal here falsely refused
    the pilot subject (round-3 re-review Important 1)."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pyproject.toml": '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
    })
    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert v.passed is True and v.waived is True


def test_waiver_ok_when_testpaths_string_contains_tests(tmp_path, monkeypatch):
    """Ini-string form with several dirs, one of them tests/ -> proceeds
    (fresh files land inside a pinned path)."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pytest.ini": "[pytest]\ntestpaths = tests other\n",
    })
    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert v.passed is True and v.waived is True


def test_waiver_ok_ini_value_with_interpolation_chars(tmp_path, monkeypatch):
    """A pytest.ini carrying %-style values (log_cli_format = %(message)s is
    the common case) must not crash the scan: ConfigParser's default
    interpolation raises InterpolationMissingOptionError -- a
    configparser.Error, not RuntimeError -- on value ACCESS, which escaped
    canary_probe as a CLI exit-1 traceback (round-3 re-review Important 2).
    No discovery keys here, so the waiver proceeds."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pytest.ini": "[pytest]\nlog_cli_format = %(message)s\n",
    })
    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert v.passed is True and v.waived is True


def test_waiver_refused_addopts_ignore_token(tmp_path, monkeypatch):
    """--ignore=... passes the bare-positional heuristic yet can kill
    fresh-file collection under tests/ -- a false WAIVE in the unsafe
    direction (round-3 re-review Minor). Refuse."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pyproject.toml": '[tool.pytest.ini_options]\naddopts = "--ignore=tests"\n',
    })
    with pytest.raises(RuntimeError, match=r"addopts in pyproject\.toml"):
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)


def test_waiver_refused_addopts_deselect_token(tmp_path, monkeypatch):
    """--deselect=... same unsafe direction as --ignore. Refuse."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pytest.ini": "[pytest]\naddopts = --deselect=tests/crucible_x_test.py\n",
    })
    with pytest.raises(RuntimeError, match=r"addopts in pytest\.ini"):
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)


def test_waiver_ok_addopts_plain_flags(tmp_path, monkeypatch):
    """addopts of plain short flags (-q -x) touches nothing -> proceeds."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pyproject.toml": '[tool.pytest.ini_options]\naddopts = "-q -x"\n',
    })
    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert v.passed is True and v.waived is True


def test_waiver_refused_setup_cfg_python_files_mismatch(tmp_path, monkeypatch):
    """Same python_files rule read via setup.cfg's [tool:pytest] section."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "setup.cfg": "[tool:pytest]\npython_files = check_*.py\n",
    })
    with pytest.raises(RuntimeError, match=r"python_files in setup\.cfg"):
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)


def test_waiver_refused_addopts_with_positional_path(tmp_path, monkeypatch):
    """addopts carrying a bare positional path token pins discovery to that
    path -- refuse (fail-safe heuristic; see _assert_fresh_file_collectable)."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pyproject.toml": '[tool.pytest.ini_options]\naddopts = "-q tests/unit"\n',
    })
    with pytest.raises(RuntimeError, match=r"addopts in pyproject\.toml"):
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)


def test_waiver_ok_addopts_flags_only(tmp_path, monkeypatch):
    """addopts of pure option flags does not touch discovery -> waiver OK."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pyproject.toml": '[tool.pytest.ini_options]\naddopts = "-q --tb=short"\n',
    })
    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert v.passed is True and v.waived is True


def test_waiver_ok_clean_pytest_section(tmp_path, monkeypatch):
    """A pytest config section defining none of the discovery keys is clean
    -> waiver OK (absent keys, like absent files, steer nothing)."""
    scope_mod, repo, fail_run = _waived_setup(monkeypatch, tmp_path, {
        "pyproject.toml": '[tool.pytest.ini_options]\nmarkers = ["slow: slow tests"]\n',
    })
    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert v.passed is True and v.waived is True


def test_canary_probe_waived_when_existing_suite_already_kills(tmp_path, monkeypatch):
    """before.killed > 0 (owner-approved two-branch amendment, 2026-07-11):
    the existing suite already proves collection under this scope, so the
    canary is never written/pristine-checked and the engine is measured
    exactly once -- `run` raising on any invocation proves no subprocess
    (the pristine pytest call) is ever made, which is only possible because
    the canary file is never written in this branch."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, killed):
            self.counts = {"killed": killed}
            self.all_mutants = 10
            self.survivors = []

    measure_calls = []

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            measure_calls.append(1)
            return FakeOutcome(3)

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n", "tests/test_mod.py": "def test_x(): pass\n"})

    def fail_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        raise AssertionError("canary_probe must not shell out when the baseline already kills")

    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert (v.kills_before, v.kills_after, v.mutants) == (3, 3, 10)
    assert v.passed is True and v.waived is True
    assert len(measure_calls) == 1
    assert not (repo / "tests" / "crucible_canary_test.py").exists()


def test_canary_probe_refuses_pristine_failing_canary(tmp_path, monkeypatch):
    """killed=0 baseline (mocked, so we reach the strict branch) but the
    freshly-written canary itself fails on pristine code -- refuse loudly
    rather than blame the subject."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, killed):
            self.counts = {"killed": killed}
            self.all_mutants = 10
            self.survivors = []

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return FakeOutcome(0)

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        class P:
            returncode, stdout, stderr = 1, "1 failed", "boom"
        return P()

    with pytest.raises(RuntimeError, match="canary failed on pristine"):
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)


@pytest.mark.slow
def test_canary_probe_real_mutmut_on_fixture_subject(subject_clone):
    """End-to-end: the same fixture mini-repo the engine's slow tests use.
    Reuse the existing committed-clone fixture from tests/test_cli.py or
    tests/test_env.py (whichever provides subject_clone); apply scope, then
    the canary must strictly increase kills."""
    from crucible.scope import apply, canary_probe, detect
    apply(subject_clone, detect(subject_clone, "subject_pkg/calc.py"))
    v = canary_probe(subject_clone, "subject_pkg/calc.py")
    assert v.passed is True


@pytest.mark.slow
def test_canary_probe_strict_branch_when_no_existing_test_touches_module(tmp_path):
    """Regression for the 2026-07-11 re-review CRITICAL: with the subject's
    tests/ dir stripped, NO existing test touches the scoped module -- the
    zero-kill baseline that is the strict branch's core case. mutmut's
    forced-fail phase (MUTANT_UNDER_TEST='fail') then relies on the CANARY
    ALONE to fail at least one test; when the canary's tolerate set swallowed
    the trampoline's MutmutProgrammaticFailException ('fail' in the tuple),
    mutmut aborted 'Unable to force test failures', every mutant landed
    not-checked, and the scope was falsely refused. The canary must let that
    exception propagate and the strict branch must clear end-to-end."""
    from crucible.scope import apply, canary_probe, detect
    subject = _clone_subject(tmp_path, strip_tests=True)
    apply(subject, detect(subject, "subject_pkg/calc.py"))
    v = canary_probe(subject, "subject_pkg/calc.py")
    assert v.passed is True
    assert v.waived is False
    assert v.kills_after > v.kills_before
