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


def test_apply_refuses_to_overwrite_existing_differing_conftest(tmp_path):
    """Finding #4: apply() must never silently clobber a subject's existing
    root conftest.py (fixtures destroyed, downstream red-suite blame lands on
    the subject). Existing content that differs from SRC_SHIM -> RuntimeError
    naming the file, and the file must be left untouched."""
    repo = _mk(tmp_path, {"src/mod.py": "X = 1\n"})
    existing = "import pytest\n\n@pytest.fixture\ndef thing():\n    return 1\n"
    (repo / "conftest.py").write_text(existing)
    with pytest.raises(RuntimeError, match="conftest.py"):
        apply(repo, detect(repo, "src/mod.py"))
    assert (repo / "conftest.py").read_text() == existing


def test_apply_is_a_noop_when_existing_conftest_is_identical_to_shim(tmp_path):
    """Identical content is a genuine no-op: apply() must proceed (not raise)
    and leave the file byte-identical."""
    repo = _mk(tmp_path, {"src/mod.py": "X = 1\n"})
    (repo / "conftest.py").write_text(SHIM)
    apply(repo, detect(repo, "src/mod.py"))  # must not raise
    assert (repo / "conftest.py").read_text() == SHIM
    assert 'source_paths = ["src/mod.py"]' in (repo / "pyproject.toml").read_text()


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


def test_canary_probe_refuses_before_writing_canary_when_module_has_no_public_names(
    tmp_path, monkeypatch,
):
    """Finding #8: an all-private/empty module (_public_top_level_names
    returns []) must refuse with a clear, honest message BEFORE writing any
    canary test file -- not fall through to the misleading 'canary failed on
    pristine code -- the probe is wrong, not the subject' path. `run` raises
    if ever called: this must be a pre-check, no subprocess, no canary file."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        counts = {"killed": 0}
        all_mutants = 10
        survivors = []

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return FakeOutcome()

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "_private = 1\n\ndef _helper():\n    pass\n"})

    def fail_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        raise AssertionError("canary_probe must not shell out when there is nothing to probe")

    with pytest.raises(RuntimeError, match="exposes no public top-level symbols"):
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert not (repo / "tests" / "crucible_canary_test.py").exists()


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


def test_canary_probe_removes_mutants_residue_on_success(tmp_path, monkeypatch):
    """Finding E leg 2: the canary probe's mutmut runs leave a mutants/ dir
    (copied tests + pycs) in the subject; downstream, harden's preflight
    pristine-suite check chokes on it (import-file-mismatch) and a retry sees
    a phantom-dirty clone. canary_probe must clean it up in a finally --
    success path here (strict branch, kills increase)."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, killed):
            self.counts = {"killed": killed}
            self.all_mutants = 10
            self.survivors = []

    measures = iter([FakeOutcome(0), FakeOutcome(2)])

    class FakeEngine:
        def __init__(self, cwd, run=None):
            self.cwd = Path(cwd)

        def measure(self):
            # what a real mutmut run leaves behind: mutants/ carrying copied tests
            (self.cwd / "mutants" / "tests").mkdir(parents=True, exist_ok=True)
            (self.cwd / "mutants" / "tests" / "test_mod.py").write_text("import mypkg\n")
            return next(measures)

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        class P:
            returncode, stdout, stderr = 0, "1 passed", ""
        return P()

    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)
    assert v.passed is True
    assert not (repo / "mutants").exists()


def test_canary_probe_removes_mutants_residue_on_refusal(tmp_path, monkeypatch):
    """Finding E leg 2, failure path: even when the probe REFUSES (here the
    waiver's discovery-config scan raises), the mutants/ residue from the
    baseline measure must not be left behind."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        counts = {"killed": 3}
        all_mutants = 10
        survivors = []

    class FakeEngine:
        def __init__(self, cwd, run=None):
            self.cwd = Path(cwd)

        def measure(self):
            (self.cwd / "mutants" / "tests").mkdir(parents=True, exist_ok=True)
            (self.cwd / "mutants" / "tests" / "test_mod.py").write_text("import mypkg\n")
            return FakeOutcome()

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        # python_files that can never match crucible_*_test.py -> waiver refused
        "pyproject.toml": '[tool.pytest.ini_options]\npython_files = ["check_*.py"]\n',
    })

    def fail_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        raise AssertionError("no subprocess expected in the waived branch")

    with pytest.raises(RuntimeError, match="python_files"):
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert not (repo / "mutants").exists()


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


def test_discovery_scan_refuses_tox_ini_python_files_mismatch(tmp_path):
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "tox.ini": "[pytest]\npython_files = check_*.py\n",
    })
    with pytest.raises(RuntimeError, match="tox.ini"):
        scope_mod._assert_fresh_file_collectable(repo)


def test_discovery_scan_ignores_tox_ini_without_pytest_section(tmp_path):
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "tox.ini": "[tox]\nenvlist = py311\n",
    })
    scope_mod._assert_fresh_file_collectable(repo)  # must not raise


# --- mutation-survivor triage (triage-A, src/crucible/scope.py) -----------


def test_top_level_imports_splits_dotted_import_to_first_segment(tmp_path):
    """`import a.b.c` binds only the top-level package `a` -- split(".")[0],
    not split(None)[0] (whitespace split, a no-op on a dotted name with no
    spaces, which would leave the whole dotted path in the set)."""
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {"probe.py": "import a.b.c\n"})
    assert scope_mod._top_level_imports(repo / "probe.py") == {"a"}


def test_top_level_imports_splits_dotted_from_import_to_first_segment(tmp_path):
    """`from pkg.sub import thing` binds the top-level package `pkg` --
    node.module.split(".")[0], not split("XX.XX")[0] (a substring absent from
    "pkg.sub", so split is a no-op and the whole dotted module leaks through)."""
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {"probe.py": "from pkg.sub import thing\n"})
    assert scope_mod._top_level_imports(repo / "probe.py") == {"pkg"}


def test_detect_notes_content_for_sandbox_hazard(tmp_path):
    """detect() must record WHICH test file and WHICH local package(s) are
    hazardous, not just that pytest_args grew -- test_detect_flags_sandbox_
    hazard_test_files only checks pytest_args, leaving the notes text (and the
    notes= constructor argument itself) unobserved."""
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "tests/test_hazard.py": "from toolbelt import helper\n",
        "toolbelt/__init__.py": "helper = 1\n",
    })
    plan = detect(repo, "mypkg/mod.py")
    assert plan.notes == [
        "tests/test_hazard.py imports local package(s) "
        "['toolbelt'] absent from mutmut's sandbox"
    ]


def test_apply_writes_conftest_and_pyproject_with_exact_lowercase_names(tmp_path, monkeypatch):
    """apply() must write to literally "conftest.py" and "pyproject.toml" --
    asserting via (repo / "conftest.py").read_text() is not enough to prove
    this on a case-insensitive filesystem (macOS default APFS), where a
    write to "CONFTEST.PY" is transparently readable back as "conftest.py".
    Spy on Path.write_text and check the exact strings passed, which is
    filesystem-case-independent."""
    calls = []
    orig_write_text = Path.write_text

    def spy_write_text(self, *a, **kw):
        calls.append(str(self))
        return orig_write_text(self, *a, **kw)

    monkeypatch.setattr(Path, "write_text", spy_write_text)
    repo = _mk(tmp_path, {"src/mod.py": "X = 1\n"})
    apply(repo, detect(repo, "src/mod.py"))
    assert any(c.endswith("/conftest.py") for c in calls)
    assert not any(c.endswith("/CONFTEST.PY") for c in calls)
    assert any(c.endswith("/pyproject.toml") for c in calls)
    assert not any(c.endswith("/PYPROJECT.TOML") for c in calls)


def test_apply_writes_pytest_args_line_when_plan_has_hazards(tmp_path):
    """apply() must forward plan.pytest_args (not a dropped/short-circuited
    None) into write_scope so the pyproject.toml [tool.mutmut] table actually
    carries the exclude-form pytest_add_cli_args_test_selection line."""
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "tests/test_hazard.py": "from toolbelt import helper\n",
        "toolbelt/__init__.py": "helper = 1\n",
    })
    plan = detect(repo, "mypkg/mod.py")
    apply(repo, plan)
    py = (repo / "pyproject.toml").read_text()
    assert 'pytest_add_cli_args_test_selection = ["--ignore=tests/test_hazard.py"]' in py


def test_public_top_level_names_excludes_private_defs(tmp_path):
    """FunctionDef/ClassDef names starting with "_" must not appear -- the
    startswith("_") check, not a string ("XX_XX") that can never match."""
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {
        "probe.py": "def pub_fn():\n    pass\n\n\ndef _priv_fn():\n    pass\n\n\n"
                    "class Pub:\n    pass\n\n\nclass _Priv:\n    pass\n",
    })
    assert scope_mod._public_top_level_names(repo / "probe.py") == ["pub_fn", "Pub"]


def test_public_top_level_names_assign_targets_exclude_private(tmp_path):
    """Module-level Assign targets follow the same public/private rule as
    defs: PUB is kept, _priv is dropped -- and the kept value is the target's
    real name (target.id), not None."""
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {"probe.py": "PUB = 1\n_priv = 2\n"})
    assert scope_mod._public_top_level_names(repo / "probe.py") == ["PUB"]


def test_public_top_level_names_skips_non_name_assignment_targets(tmp_path):
    """A tuple-unpacking assignment (`a, b = 1, 2`) has a non-Name target
    (ast.Tuple); the isinstance guard must short-circuit past it rather than
    evaluate target.id (which Tuple nodes don't have)."""
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {"probe.py": "a, b = 1, 2\nPUB = 3\n"})
    assert scope_mod._public_top_level_names(repo / "probe.py") == ["PUB"]


def test_pytest_config_sections_reads_exact_lowercase_pyproject_name(tmp_path, monkeypatch):
    """_pytest_config_sections must read literally "pyproject.toml" -- same
    case-insensitive-filesystem blind spot as the conftest.py check above;
    spy on Path.read_text and check the exact string."""
    import crucible.scope as scope_mod
    calls = []
    orig_read_text = Path.read_text

    def spy_read_text(self, *a, **kw):
        calls.append(str(self))
        return orig_read_text(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", spy_read_text)
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "pyproject.toml": '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
    })
    list(scope_mod._pytest_config_sections(repo))
    assert any(c.endswith("/pyproject.toml") for c in calls)
    assert not any(c.endswith("/PYPROJECT.TOML") for c in calls)


def test_pytest_config_sections_tool_present_without_pytest_subsection(tmp_path):
    """A pyproject.toml with a [tool.*] table but no [tool.pytest] must yield
    nothing, not crash -- `.get("pytest", {})` must default to a dict so the
    chained `.get("ini_options")` has something to call, not None."""
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "pyproject.toml": "[tool.other]\nx = 1\n",
    })
    assert list(scope_mod._pytest_config_sections(repo)) == []


def test_pytest_config_sections_no_tool_section_at_all(tmp_path):
    """A pyproject.toml with no [tool] table at all must yield nothing, not
    crash -- `.get("tool", {})` must default to a dict, not None."""
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "pyproject.toml": '[project]\nname = "x"\n',
    })
    assert list(scope_mod._pytest_config_sections(repo)) == []


def test_pytest_config_sections_ini_file_without_pytest_section(tmp_path):
    """pytest.ini exists but has no [pytest] section -- must yield nothing.
    The pre-try `section` initializer must be None (falls through the final
    `if section is not None` guard), not a falsy-but-not-None "" (which would
    wrongly pass that guard and yield an empty section)."""
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "pytest.ini": "[other]\nx = 1\n",
    })
    assert list(scope_mod._pytest_config_sections(repo)) == []


def test_pytest_config_sections_malformed_ini_raises_runtime_error_with_message(tmp_path):
    """A pytest.ini that configparser can't parse at all (no section headers)
    must raise RuntimeError carrying the real exception text, not
    RuntimeError(None)."""
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "pytest.ini": "not a valid ini file\n",
    })
    with pytest.raises(RuntimeError, match=r"^cannot parse pytest\.ini"):
        list(scope_mod._pytest_config_sections(repo))


def test_canary_probe_strips_src_prefix_from_modname(tmp_path, monkeypatch):
    """A "src/pkg/mod.py" module must import as "pkg.mod" in the canary (v7:
    bare name, never src.-qualified) -- both the startswith("src.") check
    (not a string that can never match, in either case) and the actual strip
    (not modname = None) must be intact. Inspect the canary file's content
    from inside the faked pristine subprocess call, before it gets cleaned up."""
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
    repo = _mk(tmp_path, {"src/mypkg/mod.py": "X = 1\n"})
    seen = {}

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        canary_path = Path(cwd) / "tests" / "crucible_canary_test.py"
        seen["content"] = canary_path.read_text()

        class P:
            returncode, stdout, stderr = 0, "1 passed", ""
        return P()

    scope_mod.canary_probe(repo, "src/mypkg/mod.py", run=fake_run)
    assert "import_module('mypkg.mod')" in seen["content"]


def test_canary_probe_passes_run_through_to_engine(tmp_path, monkeypatch):
    """canary_probe must construct MutmutEngine(subject_dir, run=run) --
    forwarding the caller's `run`, not dropping the kwarg so the engine falls
    back to its own default (real subprocess.run, unusable in a fast test)."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        counts = {"killed": 3}
        all_mutants = 10
        survivors = []

    captured = {}

    class FakeEngine:
        def __init__(self, cwd, run=None):
            captured["run"] = run

        def measure(self):
            return FakeOutcome()

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})

    def fail_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        raise AssertionError("canary_probe must not shell out in the waived branch")

    scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert captured["run"] is fail_run


def test_canary_probe_defaults_missing_before_killed_count_to_zero(tmp_path, monkeypatch):
    """When the engine's baseline Outcome carries no "killed" key at all
    (counts={}), before_killed must default to 0 (the zero-coverage strict-
    branch case), not crash on int(None) and not silently default to 1 (which
    would wrongly waive a subject with zero real kills)."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, counts):
            self.counts = counts
            self.all_mutants = 10
            self.survivors = []

    measures = iter([FakeOutcome({}), FakeOutcome({"killed": 2})])

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
    assert v.kills_before == 0
    assert v.waived is False
    assert v.passed is True


def test_canary_probe_waives_at_exactly_one_kill(tmp_path, monkeypatch):
    """The waiver boundary is `before_killed > 0` -- a single kill already
    proves collection, so kills_before == 1 must waive immediately (no second,
    strict-branch measurement), not require kills_before > 1."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        counts = {"killed": 1}
        all_mutants = 10
        survivors = []

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return FakeOutcome()

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})

    def fail_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        raise AssertionError("must not shell out when kills_before == 1 (waived)")

    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert v.waived is True and v.kills_before == 1


def test_canary_probe_pristine_subprocess_call_arguments(tmp_path, monkeypatch):
    """The pristine canary check must be invoked with cwd=str(subject_dir),
    capture_output=True, text=True, timeout=300, and the pytest cmd -- every
    one of those, not a dropped kwarg (silently defaulting to something else)
    or a nearby-but-wrong value. Use sentinel defaults in the fake `run` so an
    OMITTED kwarg is distinguishable from one explicitly passed the "correct"
    value."""
    import crucible.scope as scope_mod

    _MISSING = object()

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
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})
    calls = []

    def fake_run(cmd, cwd=_MISSING, capture_output=_MISSING, text=_MISSING, timeout=_MISSING, **kw):
        calls.append(dict(cmd=cmd, cwd=cwd, capture_output=capture_output,
                           text=text, timeout=timeout))

        class P:
            returncode, stdout, stderr = 0, "1 passed", ""
        return P()

    scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)
    assert len(calls) == 1
    call = calls[0]
    assert call["cwd"] == str(repo)
    assert call["capture_output"] is True
    assert call["text"] is True
    assert call["timeout"] == 300
    assert call["cmd"][:3] == [sys.executable, "-m", "pytest"]


def test_canary_probe_pristine_failure_message_empty_stdout(tmp_path, monkeypatch):
    """With empty pristine stdout, the RuntimeError message must be exactly
    the fixed prefix -- not wrapped in extra "XX" marker text, and not padded
    with a non-empty placeholder in place of the (correctly empty) fallback."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        counts = {"killed": 0}
        all_mutants = 10
        survivors = []

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return FakeOutcome()

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        class P:
            returncode, stdout, stderr = 1, "", "boom"
        return P()

    with pytest.raises(RuntimeError) as exc_info:
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)
    assert str(exc_info.value) == (
        "canary failed on pristine code -- the probe is wrong, not the subject: ")


def test_canary_probe_pristine_failure_message_uses_stdout_tail(tmp_path, monkeypatch):
    """With a long pristine stdout, the RuntimeError message must end with
    exactly the LAST 400 characters (stdout[-400:], not stdout[400:] which
    slices from the front, and not stdout[-401:] which is one character too
    many) -- and it must actually be the stdout content, not a dropped-to-''
    placeholder from a mangled `or`."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        counts = {"killed": 0}
        all_mutants = 10
        survivors = []

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return FakeOutcome()

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})
    stdout_text = "".join(f"line{i}\n" for i in range(100))
    assert len(stdout_text) > 401  # long enough to distinguish -400 from -401 and +400

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        class P:
            returncode, stdout, stderr = 1, stdout_text, ""
        return P()

    with pytest.raises(RuntimeError) as exc_info:
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)
    expected = ("canary failed on pristine code -- the probe is wrong, not the subject: "
                + stdout_text[-400:])
    assert str(exc_info.value) == expected


def test_canary_probe_unlink_tolerates_already_missing_canary_file(tmp_path, monkeypatch):
    """The canary file is written just before the pristine subprocess call
    and always removed in a `finally` -- that removal must tolerate the file
    already being gone (missing_ok=True), e.g. if the pristine pytest
    invocation itself (or subject-side tooling) already deleted it, not raise
    FileNotFoundError and mask a real result."""
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
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        (repo / "tests" / "crucible_canary_test.py").unlink()  # simulate external removal
        class P:
            returncode, stdout, stderr = 0, "1 passed", ""
        return P()

    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)
    assert v.passed is True


def test_canary_probe_defaults_missing_after_killed_count_to_zero(tmp_path, monkeypatch):
    """Same as the before_killed default-to-zero rule, for the second (after)
    measurement: a counts dict with no "killed" key must yield after_killed
    == 0, not crash on int(None) and not silently default to 1."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, counts):
            self.counts = counts
            self.all_mutants = 10
            self.survivors = []

    measures = iter([FakeOutcome({"killed": 0}), FakeOutcome({})])

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
    assert v.kills_after == 0
    assert v.passed is False


def test_canary_probe_reports_after_measurement_mutant_count(tmp_path, monkeypatch):
    """CanaryVerdict.mutants must be the SECOND (after) measurement's
    all_mutants, not None -- use distinct before/after values so a mixup is
    also observable, not just a dropped field."""
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, killed, all_mutants):
            self.counts = {"killed": killed}
            self.all_mutants = all_mutants
            self.survivors = []

    measures = iter([FakeOutcome(0, 7), FakeOutcome(2, 42)])

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
    assert v.mutants == 42


def test_canary_probe_removes_exact_lowercase_mutants_dirname(tmp_path, monkeypatch):
    """The residue cleanup must target literally "mutants" -- spy on
    shutil.rmtree (as called from inside crucible.scope) and check the exact
    path string, which is filesystem-case-independent (unlike asserting the
    directory is merely gone, which a case-insensitive filesystem would
    satisfy even for an "MUTANTS" rmtree call)."""
    import crucible.scope as scope_mod
    calls = []
    orig_rmtree = shutil.rmtree

    def spy_rmtree(path, *a, **kw):
        calls.append(str(path))
        return orig_rmtree(path, *a, **kw)

    monkeypatch.setattr(scope_mod.shutil, "rmtree", spy_rmtree)

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
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})

    def fail_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        raise AssertionError("no subprocess expected in the waived branch")

    scope_mod.canary_probe(repo, "mypkg/mod.py", run=fail_run)
    assert any(c.endswith("/mutants") for c in calls)
    assert not any(c.endswith("/MUTANTS") for c in calls)


def test_discovery_scan_names_pyproject_in_unparseable_refusal(tmp_path):
    # Kills x__pytest_config_sections__mutmut_7: the refusal for an unparseable
    # pyproject.toml must NAME the file (RuntimeError(None) is useless to a user).
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "pyproject.toml": "[tool.pytest.ini_options\nbroken = true\n",  # invalid TOML
    })
    with pytest.raises(RuntimeError, match="pyproject.toml"):
        scope_mod._assert_fresh_file_collectable(repo)


# ── Survivor triage 2026-07-13 ────────────────────────────────────────────────
# The mutation gate found 7 survivors in scope.py, all of them string-literal
# mutants inside REFUSAL messages: apply's conftest-collision guidance
# (mutmut 10-14) and canary_probe's no-public-API refusal (mutmut 52-53). None
# were equivalent -- they survived only because the existing tests asserted a
# fragment of each message (match="conftest.py") instead of the message.
#
# A refusal message IS the product on those paths: it is the entire value the
# user gets when crucible declines to run. Asserting that it merely "contains
# conftest.py" leaves the actual instructions free to rot into nonsense.
#
# Pinned by EXACT EQUALITY, not substring. A substring assertion does not kill
# these: the mutant that wraps the text in XX..XX still CONTAINS the original,
# so `expected in actual` passes on the corrupted string. (Same trap as an
# unanchored pytest.raises(match=...) -- see tests/test_score.py.)

def test_apply_conftest_collision_message_is_pinned_exactly(tmp_path):
    repo = _mk(tmp_path, {"src/mod.py": "X = 1\n"})
    conftest = repo / "conftest.py"
    conftest.write_text("import pytest\n")

    with pytest.raises(RuntimeError) as exc:
        apply(repo, detect(repo, "src/mod.py"))

    assert str(exc.value) == (
        f"{conftest} already exists and differs from crucible's src/ sys.path "
        "shim; subject has a root conftest.py -- crucible will not overwrite it. "
        "Merge the src/ sys.path shim yourself or move your conftest."
    )


def test_canary_probe_no_public_api_message_is_pinned_exactly(tmp_path, monkeypatch):
    import crucible.scope as scope_mod

    class FakeOutcome:
        counts = {"killed": 0}
        all_mutants = 10
        survivors = []

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return FakeOutcome()

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "_private = 1\n"})

    with pytest.raises(RuntimeError) as exc:
        scope_mod.canary_probe(repo, "mypkg/mod.py")

    assert str(exc.value) == (
        "module mypkg/mod.py exposes no public top-level symbols to probe; "
        "point crucible at a module with public API"
    )
