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
