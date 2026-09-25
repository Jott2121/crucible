"""The number users see, end to end: `crucible score` output and the Action that
turns its JSON into a PR comment, a step output, and a fail-under message.

The Action's logic lives in Python heredocs inside action.yml, which nothing
exercised. That is how every one of its survivor counts read mutmut's narrow
"survived" field and printed "Every injected defect was killed." over a 33%
score. These tests run that embedded Python for real, against JSON produced by
the real `crucible score` command.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import crucible.engine as engine_mod
from crucible import cli
from crucible.engine import MutationOutcome

ACTION = Path(__file__).resolve().parent.parent / "action.yml"

# one tested function, one untested one: the live repro
UNTESTED = MutationOutcome(
    counts={"killed": 1, "survived": 0, "total": 3, "no_tests": 2, "skipped": 0,
            "suspicious": 0, "timeout": 0, "check_was_interrupted_by_user": 0,
            "segfault": 0},
    survivors=["pkg.calc.x_clamp__mutmut_1", "pkg.calc.x_clamp__mutmut_2"],
    all_mutants=3,
)
ALL_KILLED = MutationOutcome(
    counts={"killed": 3, "survived": 0, "total": 3, "no_tests": 0, "timeout": 0},
    survivors=[], all_mutants=3,
)
TIMEOUTS_ONLY = MutationOutcome(
    counts={"killed": 2, "survived": 0, "total": 3, "no_tests": 0, "timeout": 1},
    survivors=[], all_mutants=3,
)


def _subject(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\n\n[tool.mutmut]\nsource_paths = ["pkg/calc.py"]\n')
    return tmp_path


def _fake_engine(monkeypatch, outcome: MutationOutcome) -> None:
    class FakeEngine:
        def __init__(self, cwd):
            self.cwd = cwd

        def measure(self):
            return outcome

    monkeypatch.setattr(engine_mod, "MutmutEngine", FakeEngine)


def _score_json(tmp_path, monkeypatch, capsys, outcome) -> dict:
    _fake_engine(monkeypatch, outcome)
    assert cli.main(["score", str(_subject(tmp_path)), "--json"]) == 0
    return json.loads(capsys.readouterr().out)


# --- crucible score ----------------------------------------------------------------

def test_score_json_reports_never_executed_mutants_as_undetected(tmp_path, monkeypatch, capsys):
    d = _score_json(tmp_path, monkeypatch, capsys, UNTESTED)
    assert d["undetected"] == 2
    assert d["survivors"] == UNTESTED.survivors
    assert d["counts"] == UNTESTED.counts          # raw mutmut counts pass through untouched


def test_score_text_headline_agrees_with_the_survivor_list_under_it(tmp_path, monkeypatch, capsys):
    _fake_engine(monkeypatch, UNTESTED)
    assert cli.main(["score", str(_subject(tmp_path))]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == ("2 of 3 injected defects SURVIVED this suite "
                      "(1 killed, mutation score 33%). "
                      "2 of them were never executed by any test.")
    assert "survivors (2):" in out


def test_score_refuses_when_mutmuts_counts_and_its_survivor_list_disagree(
        tmp_path, monkeypatch, capsys):
    # mutmut's summary stats and its per-mutant listing are two separate sources.
    # If they disagree, any number printed is a guess, so the tool must refuse.
    disagree = MutationOutcome(
        counts={"killed": 3, "survived": 0, "total": 3, "no_tests": 0},
        survivors=["pkg.calc.x_clamp__mutmut_1"], all_mutants=3)
    _fake_engine(monkeypatch, disagree)
    assert cli.main(["score", str(_subject(tmp_path)), "--json"]) == 4
    captured = capsys.readouterr()
    assert captured.out == ""                      # nothing half-written to the JSON file
    assert captured.err.startswith("REFUSING: ")
    assert "0 undetected" in captured.err and "1 survivor" in captured.err


# --- action.yml ---------------------------------------------------------------------

def _action_step_python(step_name: str) -> str:
    """The Python heredoc inside the named step of action.yml, dedented."""
    text = ACTION.read_text()
    steps = re.split(r"^    - name: ", text, flags=re.M)
    matches = [s for s in steps if s.startswith(step_name + "\n")]
    assert len(matches) == 1, f"expected exactly one action step named {step_name!r}"
    body = re.search(r"python - <<'PY'[^\n]*\n(.*?)\n\s*PY\n", matches[0], re.S)
    assert body, f"no python heredoc in action step {step_name!r}"
    return textwrap.dedent(body.group(1))


def _run_action_step(step_name, score_json, tmp_path, env=None):
    (tmp_path / "crucible-score.json").write_text(json.dumps(score_json))
    return subprocess.run(
        [sys.executable, "-"], input=_action_step_python(step_name), text=True,
        capture_output=True, cwd=tmp_path, env={**(env or {}), "PATH": ""})


@pytest.fixture
def untested_json(tmp_path, monkeypatch, capsys):
    return _score_json(tmp_path, monkeypatch, capsys, UNTESTED)


def test_action_survived_output_counts_never_executed_mutants(untested_json, tmp_path):
    proc = _run_action_step("Score the suite", untested_json, tmp_path)
    assert proc.returncode == 0, proc.stderr
    outputs = dict(line.split("=", 1) for line in proc.stdout.splitlines())
    assert outputs == {"score": "33.33", "killed": "1", "survived": "2", "total": "3"}


def test_action_pr_comment_never_claims_every_defect_was_killed_over_survivors(
        untested_json, tmp_path):
    proc = _run_action_step("Comment on the PR", untested_json, tmp_path)
    assert proc.returncode == 0, proc.stderr
    comment = proc.stdout
    assert "Every injected defect was killed" not in comment
    assert "> **2 defects survived**" in comment
    assert "> 2 of them were never executed by any test." in comment
    assert "pkg.calc.x_clamp__mutmut_1" in comment and "pkg.calc.x_clamp__mutmut_2" in comment


def test_action_pr_comment_celebrates_only_a_suite_that_killed_everything(
        tmp_path, monkeypatch, capsys):
    d = _score_json(tmp_path, monkeypatch, capsys, ALL_KILLED)
    proc = _run_action_step("Comment on the PR", d, tmp_path)
    assert "> **Every injected defect was killed.**" in proc.stdout
    assert "survived" not in proc.stdout


def test_action_pr_comment_does_not_call_a_timeout_a_kill(tmp_path, monkeypatch, capsys):
    d = _score_json(tmp_path, monkeypatch, capsys, TIMEOUTS_ONLY)
    proc = _run_action_step("Comment on the PR", d, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "Every injected defect was killed" not in proc.stdout
    assert "> **No injected defect survived.** 1 timed out" in proc.stdout


def test_action_fail_under_message_counts_never_executed_mutants(untested_json, tmp_path):
    proc = _run_action_step("Enforce the floor", untested_json, tmp_path,
                            env={"FAIL_UNDER": "50"})
    assert proc.returncode == 1
    assert "2 injected defects survived this suite." in proc.stdout
