from pathlib import Path

import pytest

from crucible.engine import MutationOutcome, MutmutEngine, ScopeError, write_scope

RESULTS = """\
    subject_pkg.calc.x_clamp__mutmut_1: killed
    subject_pkg.calc.x_clamp__mutmut_2: survived
    subject_pkg.calc.x_rate__mutmut_1: survived
"""


class FakeRun:
    """Scripted subprocess.run: returns canned (returncode, stdout) by command."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def __call__(self, cmd, cwd=None, capture_output=True, text=True):
        self.calls.append(cmd)
        key = " ".join(cmd[2:])  # drop "python -m"
        rc, out = self.script.get(key, (0, ""))

        class P:
            returncode, stdout, stderr = rc, out, ""

        return P()


def test_measure_returns_survivor_ids(tmp_path):
    (tmp_path / "mutants").mkdir()
    (tmp_path / "mutants" / "mutmut-cicd-stats.json").write_text(
        '{"killed": 1, "survived": 2, "no_coverage": 0, "timeout": 0}'
    )
    run = FakeRun({
        "mutmut --version": (0, "mutmut, version 3.6.0"),
        "mutmut run": (2, ""),
        "mutmut export-cicd-stats": (0, ""),
        "mutmut results --all true": (0, RESULTS),
    })
    outcome = MutmutEngine(tmp_path, run=run).measure()
    assert isinstance(outcome, MutationOutcome)
    assert outcome.survivors == [
        "subject_pkg.calc.x_clamp__mutmut_2",
        "subject_pkg.calc.x_rate__mutmut_1",
    ]
    assert outcome.all_mutants == 3


def test_survivor_diff_shells_to_mutmut_show(tmp_path):
    run = FakeRun({"mutmut show subject_pkg.calc.x_clamp__mutmut_2": (0, "--- diff ---")})
    diff = MutmutEngine(tmp_path, run=run).survivor_diff("subject_pkg.calc.x_clamp__mutmut_2")
    assert diff == "--- diff ---"


def test_write_scope_appends_table(tmp_path):
    py = tmp_path / "pyproject.toml"
    py.write_text('[project]\nname = "subject"\n')
    write_scope(py, ["subject_pkg/calc.py"])
    text = py.read_text()
    assert "[tool.mutmut]" in text and 'source_paths = ["subject_pkg/calc.py"]' in text


def test_write_scope_replaces_existing_table(tmp_path):
    py = tmp_path / "pyproject.toml"
    py.write_text('[project]\nname = "s"\n\n[tool.mutmut]\nsource_paths = ["old.py"]\n')
    write_scope(py, ["new.py"])
    text = py.read_text()
    assert 'source_paths = ["new.py"]' in text and "old.py" not in text


def test_write_scope_requires_pyproject(tmp_path):
    with pytest.raises(ScopeError):
        write_scope(tmp_path / "pyproject.toml", ["x.py"])
