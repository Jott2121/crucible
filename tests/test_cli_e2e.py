"""The integration proof: real mutmut, real pytest, fake model. Marked slow (seconds on the tiny fixture)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

GOOD_TESTS = """```python
from subject_pkg.calc import acceptance_rate, clamp


def test_clamp_below():
    assert clamp(-1, 0, 10) == 0


def test_clamp_above():
    assert clamp(11, 0, 10) == 10


def test_clamp_inside():
    assert clamp(3, 0, 10) == 3


def test_rate():
    assert acceptance_rate(10, 5) == 0.5


def test_rate_zero_offers():
    assert acceptance_rate(0, 0) == 0.0


def test_rate_negative_offers():
    assert acceptance_rate(-3, 1) == 0.0
```"""


@pytest.mark.slow
def test_oneshot_end_to_end(tmp_path):
    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    # subject package importable by pytest/mutmut inside the crucible venv
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(subject)], check=True)

    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps([GOOD_TESTS]))

    from crucible.cli import main
    rc = main(["oneshot", str(subject), "--module", "subject_pkg/calc.py",
               "--tester", "fake", "--critic", "fake",
               "--fake-replies", str(replies), "--runs-dir", str(tmp_path / "runs")])
    assert rc == 0

    runs = list((tmp_path / "runs").iterdir())
    assert len(runs) == 1
    receipt = (runs[0] / "receipt.jsonl").read_text().strip().splitlines()
    round0 = json.loads(receipt[0])
    assert round0["role"] == "tester" and round0["status"] == "ok"
    assert round0["survivors_after"], "round 0 must measure real survivors"
    result = json.loads((runs[0] / "result.json").read_text())
    assert result["verdict"] in ("clean", "oneshot")


WEAK_TESTS = """```python
from subject_pkg.calc import clamp


def test_clamp_inside():
    assert clamp(3, 0, 10) == 3
```"""


@pytest.mark.slow
def test_harden_end_to_end_survives_engine_artifacts(tmp_path):
    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(subject)], check=True)

    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps([WEAK_TESTS, GOOD_TESTS]))

    from crucible.cli import main
    rc = main(["harden", str(subject), "--module", "subject_pkg/calc.py",
               "--tester", "fake", "--critic", "fake", "--rounds", "1",
               "--fake-replies", str(replies), "--runs-dir", str(tmp_path / "runs")])
    assert rc == 0

    runs = list((tmp_path / "runs").iterdir())
    receipt = [json.loads(l) for l in (runs[0] / "receipt.jsonl").read_text().strip().splitlines()]
    assert receipt[0]["survivors_after"], "weak tester must leave survivors"
    # the critical assertion: round 1 must NOT be rejected by its own engine's artifacts
    assert receipt[1]["status"] == "ok"
    assert receipt[1]["kills"], "critic round must kill at least one named survivor"
    # receipts carry the full denominator + provenance
    result = json.loads((runs[0] / "result.json").read_text())
    assert result["baseline_all_mutants"] > 0
    meta = json.loads((runs[0] / "meta.json").read_text())
    assert meta["tester_provider"] == "fake"
    assert meta["crucible_version"] and meta["mutmut_version"] and meta["oracle_gate_version"]
    # the report command must consume the receipts this very run just wrote
    assert main(["report", str(runs[0])]) == 0

    # the scope `crucible scope`'s canary would have validated (also_copy
    # derived from scope.detect) must be what preflight actually commits --
    # not a bare source_paths that silently drops it (Opus review, scope->harden
    # handoff defect: cli.py's _cmd_run was building SubjectEnv with scope=None).
    committed_pyproject = subprocess.run(
        ["git", "show", "HEAD:pyproject.toml"], cwd=subject,
        capture_output=True, text=True, check=True,
    ).stdout
    assert 'also_copy = ["subject_pkg"]' in committed_pyproject


@pytest.mark.slow
def test_harden_completes_after_scope_commit_with_leftover_mutants_dir(tmp_path):
    """Finding D sequence test (Opus re-review of b0402fc): the exact operator
    flow the harden-tests skill prescribes -- `crucible scope` writes the
    config (its canary probe leaves an untracked mutants/ dir behind), the
    operator commits pyproject.toml/conftest.py per skill step 4, then runs
    `crucible harden`. Preflight's dirty-check passes (mutants/ is a filtered
    engine artifact) and the scope write is byte-identical (fix B), so there
    is genuinely nothing to commit -- but the commit TRIGGER at env.py:118
    read raw `git status --porcelain -uall`, saw `?? mutants/`, staged
    nothing, and crashed on `git commit` ("nothing to commit"). The whole
    run must complete instead.

    Finding E upgrade: the residue is now REALISTIC -- mutants/ carrying a
    copy of tests/test_calc.py (what mutmut's sandbox actually contains),
    which a synthetic junk.json could never reproduce: without run_tests's
    --ignore=mutants, preflight's root pytest run collects BOTH copies of
    test_calc.py, dies on the import-file-mismatch/duplicate-module
    collection error, and falsely reports 'subject suite is red on pristine
    code'. Covers the manual-mutmut-run case leg 2's own cleanup cannot."""
    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(subject)], check=True)

    # `crucible scope`'s file writes, committed per skill step 4 (this fixture
    # is not src-layout, so there is no conftest.py -- the skill's command
    # tolerates that)
    from crucible.scope import apply, detect
    apply(subject, detect(subject, "subject_pkg/calc.py"))
    subprocess.run(["git", "add", "pyproject.toml"], cwd=subject, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm",
         "crucible: scope config for subject_pkg/calc.py"],
        cwd=subject, check=True,
    )
    # what a mutmut run actually leaves behind, untracked: the sandbox copy of
    # the test suite (plus bookkeeping), whose duplicate test module names are
    # what break an unshielded root pytest run
    (subject / "mutants" / "tests").mkdir(parents=True)
    shutil.copy(subject / "tests" / "test_calc.py", subject / "mutants" / "tests" / "test_calc.py")
    (subject / "mutants" / "junk.json").write_text("{}")

    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps([WEAK_TESTS, GOOD_TESTS]))

    from crucible.cli import main
    rc = main(["harden", str(subject), "--module", "subject_pkg/calc.py",
               "--tester", "fake", "--critic", "fake", "--rounds", "1",
               "--fake-replies", str(replies), "--runs-dir", str(tmp_path / "runs")])
    assert rc == 0


@pytest.mark.slow
def test_real_scope_cli_then_skill_commit_then_harden_completes(tmp_path):
    """Finding E, the test the reviewer demanded: the REAL end-to-end operator
    flow with no synthetic residue at all. Run the actual `crucible scope`
    CLI (its canary probe runs real mutmut, leaving whatever it really
    leaves), commit the scope config exactly as harden-tests SKILL.md step 4
    prescribes, then run `crucible harden --tester fake`. The whole flow must
    complete: scope rc 0, harden rc 0."""
    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(subject)], check=True)

    from crucible.cli import main
    rc = main(["scope", str(subject), "--module", "subject_pkg/calc.py"])
    assert rc == 0

    # skill step 4, verbatim shape (no conftest.py here: non-src layout)
    subprocess.run(["git", "add", "pyproject.toml"], cwd=subject, check=True)
    if (subject / "conftest.py").is_file():
        subprocess.run(["git", "add", "conftest.py"], cwd=subject, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm",
         "crucible: scope config for subject_pkg/calc.py"],
        cwd=subject, check=True,
    )

    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps([WEAK_TESTS, GOOD_TESTS]))
    rc = main(["harden", str(subject), "--module", "subject_pkg/calc.py",
               "--tester", "fake", "--critic", "fake", "--rounds", "1",
               "--fake-replies", str(replies), "--runs-dir", str(tmp_path / "runs")])
    assert rc == 0


ALL_WRONG_TESTS = """```python
from subject_pkg.calc import acceptance_rate


def test_wrong_oracle_a():
    assert acceptance_rate(10, 5) == 0.99


def test_wrong_oracle_b():
    assert acceptance_rate(1, 1) == 0.5
```"""


@pytest.mark.slow
def test_cli_run_preserves_rejected_test_file_under_run_dir(tmp_path):
    """Gate-7 live defect 3: run_arm wires env.set_artifact_dir(run_dir) so a
    rejected test file is preserved as evidence; _cmd_run never did, so the
    first live run's rejected tester file was DELETED -- violating the
    never-discarded posture (spec: a rejected test is never counted as a
    kill, but never thrown away either). A fake tester whose tests all carry
    wrong oracles forces a rejected round; the file must land under
    <run_dir>/rejected/ and be gone from the subject clone."""
    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(subject)], check=True)

    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps([ALL_WRONG_TESTS]))

    from crucible.cli import main
    rc = main(["oneshot", str(subject), "--module", "subject_pkg/calc.py",
               "--tester", "fake", "--critic", "fake",
               "--fake-replies", str(replies), "--runs-dir", str(tmp_path / "runs")])
    assert rc == 3  # rejected round -> rejected verdict

    run_dir = next((tmp_path / "runs").iterdir())
    preserved = list((run_dir / "rejected").glob("*.py"))
    assert preserved, "rejected test file must be preserved under <run_dir>/rejected/"
    assert "test_wrong_oracle_a" in preserved[0].read_text()
    # and it leaves no trace in the subject clone
    assert not list((subject / "tests").glob("crucible_*_test.py"))


@pytest.mark.slow
def test_cli_meta_records_billing(tmp_path):
    # FakeProvider carries no billing attribute -> getattr(..., "billing", "api")
    # default must land in meta.json for both roles.
    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(subject)], check=True)

    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps([GOOD_TESTS]))

    from crucible.cli import main
    rc = main(["oneshot", str(subject), "--module", "subject_pkg/calc.py",
               "--tester", "fake", "--critic", "fake",
               "--fake-replies", str(replies), "--runs-dir", str(tmp_path / "runs")])
    assert rc == 0

    run_dir = next((tmp_path / "runs").iterdir())
    meta = json.loads((run_dir / "meta.json").read_text())
    assert meta["tester_billing"] == "api"
    assert meta["critic_billing"] == "api"
