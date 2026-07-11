import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from crucible.scope import ScopePlan, apply, detect

SHIM = 'import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))\n'


@pytest.fixture
def subject_clone(tmp_path):
    """Committed git clone of tests/fixtures/subject, installed editable into
    this venv -- mirrors the inline-clone pattern in tests/test_cli_e2e.py
    (no shared `subject_clone` fixture exists elsewhere in the repo; this is
    the first one, scoped locally to this test module)."""
    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(subject)], check=True)
    return subject


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
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, killed):
            self.counts = {"killed": killed}
            self.all_mutants = 10
            self.survivors = []

    measures = iter([FakeOutcome(3), FakeOutcome(5)])

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
    assert v.passed is True and (v.kills_before, v.kills_after) == (3, 5)
    assert not (repo / "tests" / "crucible_canary_test.py").exists()  # cleaned up


def test_canary_probe_fails_when_kills_flat(tmp_path, monkeypatch):
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, killed):
            self.counts = {"killed": killed}
            self.all_mutants = 10
            self.survivors = []

    measures = iter([FakeOutcome(3), FakeOutcome(3)])

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


def test_canary_probe_refuses_pristine_failing_canary(tmp_path, monkeypatch):
    import crucible.scope as scope_mod
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
