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


def test_write_scope_requires_pyproject_even_with_create_if_missing_false(tmp_path):
    with pytest.raises(ScopeError):
        write_scope(tmp_path / "pyproject.toml", ["x.py"], create_if_missing=False)


def test_write_scope_creates_pyproject_when_missing_and_create_if_missing_true(tmp_path):
    py = tmp_path / "pyproject.toml"
    assert not py.exists()
    write_scope(py, ["src/train.py"], also_copy=["src", "data"], create_if_missing=True)
    assert py.exists()
    text = py.read_text()
    assert "# created by crucible preflight" in text
    assert "[tool.mutmut]" in text
    assert 'source_paths = ["src/train.py"]' in text
    assert 'also_copy = ["src", "data"]' in text
    # ONLY the mutmut scope table -- crucible never invents real project metadata
    assert "[project]" not in text
    assert "[build-system]" not in text


def test_write_scope_create_if_missing_does_not_disturb_an_existing_file(tmp_path):
    py = tmp_path / "pyproject.toml"
    py.write_text('[project]\nname = "s"\n')
    write_scope(py, ["pkg/mod.py"], create_if_missing=True)
    text = py.read_text()
    assert '[project]\nname = "s"' in text
    assert "[tool.mutmut]" in text


def test_write_scope_includes_also_copy_when_given(tmp_path):
    py = tmp_path / "pyproject.toml"
    py.write_text('[project]\nname = "s"\n')
    write_scope(py, ["pkg/mod.py"], also_copy=["pkg"])
    text = py.read_text()
    assert "[tool.mutmut]" in text
    assert 'source_paths = ["pkg/mod.py"]' in text
    assert 'also_copy = ["pkg"]' in text


def test_write_scope_omits_also_copy_when_none(tmp_path):
    py = tmp_path / "pyproject.toml"
    py.write_text('[project]\nname = "s"\n')
    write_scope(py, ["pkg/mod.py"])
    text = py.read_text()
    assert "also_copy" not in text


def test_write_scope_includes_pytest_args_when_given(tmp_path):
    py = tmp_path / "pyproject.toml"
    py.write_text('[project]\nname = "s"\n')
    write_scope(py, ["pkg/mod.py"], pytest_args=["tests/test_mod.py"])
    text = py.read_text()
    assert 'pytest_add_cli_args_test_selection = ["tests/test_mod.py"]' in text


def test_write_scope_omits_pytest_args_when_none(tmp_path):
    py = tmp_path / "pyproject.toml"
    py.write_text('[project]\nname = "s"\n')
    write_scope(py, ["pkg/mod.py"])
    text = py.read_text()
    assert "pytest_add_cli_args_test_selection" not in text


def test_write_scope_replace_still_works_with_also_copy(tmp_path):
    py = tmp_path / "pyproject.toml"
    py.write_text(
        '[project]\nname = "s"\n\n[tool.mutmut]\nsource_paths = ["old.py"]\nalso_copy = ["old"]\n'
    )
    write_scope(py, ["new.py"], also_copy=["newpkg"])
    text = py.read_text()
    assert 'source_paths = ["new.py"]' in text
    assert 'also_copy = ["newpkg"]' in text
    assert "old.py" not in text and '"old"' not in text


def test_measure_reraises_unclassified_status_as_runtime_error(tmp_path):
    (tmp_path / "mutants").mkdir()
    (tmp_path / "mutants" / "mutmut-cicd-stats.json").write_text(
        '{"killed": 0, "survived": 0, "no_coverage": 0, "timeout": 0}'
    )
    run = FakeRun({
        "mutmut --version": (0, "mutmut, version 3.6.0"),
        "mutmut run": (2, ""),
        "mutmut export-cicd-stats": (0, ""),
        "mutmut results --all true": (0, "    subject_pkg.calc.x_clamp__mutmut_1: not checked\n"),
        # scripted "pytest -q" rc=2 (a real failure/usage error, neither 0 nor
        # 5) -- NOT the zero-test case, so the loud error must still fire.
        "pytest -q --ignore=mutants": (2, "INTERNALERROR"),
    })
    with pytest.raises(RuntimeError, match="mutmut evaluated no mutants"):
        MutmutEngine(tmp_path, run=run).measure()


def test_measure_treats_all_not_checked_as_zero_test_baseline_when_no_tests_exist(tmp_path):
    """Every mutant "not checked" + a bare `pytest -q` confirming zero tests
    exist anywhere (exit 5) is the legitimate pristine baseline for a stripped
    third-party subject (protocol §3: "genuinely empty starting suite") --
    mutmut's own stats phase hard-fails on zero tests rather than reporting 0%
    coverage, but an empty suite provably kills nothing, so every mutant is a
    survivor by construction, not a guess."""
    (tmp_path / "mutants").mkdir()
    (tmp_path / "mutants" / "mutmut-cicd-stats.json").write_text(
        '{"killed": 0, "survived": 0, "no_coverage": 0, "timeout": 0}'
    )
    run = FakeRun({
        "mutmut --version": (0, "mutmut, version 3.6.0"),
        "mutmut run": (1, ""),
        "mutmut export-cicd-stats": (0, ""),
        "mutmut results --all true": (0,
            "    subject_pkg.calc.x_clamp__mutmut_1: not checked\n"
            "    subject_pkg.calc.x_rate__mutmut_1: not checked\n"),
        "pytest -q --ignore=mutants": (5, "no tests ran in 0.01s"),
    })
    outcome = MutmutEngine(tmp_path, run=run).measure()
    assert outcome.survivors == [
        "subject_pkg.calc.x_clamp__mutmut_1",
        "subject_pkg.calc.x_rate__mutmut_1",
    ]
    assert outcome.all_mutants == 2
    assert outcome.counts["killed"] == 0
    assert outcome.counts["survived"] == 2


def test_measure_treats_all_not_checked_as_zero_test_baseline_when_suite_is_green_but_uncovered(tmp_path):
    """Every mutant "not checked" + a bare `pytest -q` that PASSES (exit 0) is
    the other legitimate case: a real, passing test suite that just never
    happens to execute the mutated module (e.g. attrition-risk-ml's train.py,
    protocol §3.1's pre-declared "degenerate maximal-headroom false-pass
    case"). This is provably zero coverage, not a guess -- the suite ran
    clean, it just never touched this file."""
    (tmp_path / "mutants").mkdir()
    (tmp_path / "mutants" / "mutmut-cicd-stats.json").write_text(
        '{"killed": 0, "survived": 0, "no_coverage": 0, "timeout": 0}'
    )
    run = FakeRun({
        "mutmut --version": (0, "mutmut, version 3.6.0"),
        "mutmut run": (1, ""),
        "mutmut export-cicd-stats": (0, ""),
        "mutmut results --all true": (0, "    subject_pkg.calc.x_clamp__mutmut_1: not checked\n"),
        "pytest -q --ignore=mutants": (0, "5 passed in 0.5s"),
    })
    outcome = MutmutEngine(tmp_path, run=run).measure()
    assert outcome.survivors == ["subject_pkg.calc.x_clamp__mutmut_1"]
    assert outcome.all_mutants == 1


def test_measure_reraises_when_pytest_confirms_a_real_error(tmp_path):
    """All-"not checked" alone is not enough: if a bare `pytest -q` does NOT
    confirm either legitimate zero-coverage case (e.g. a real collection
    error elsewhere, exit 1/2 rather than 0/5), this is a genuine scope bug
    and must still fail loud rather than being silently treated as valid."""
    (tmp_path / "mutants").mkdir()
    (tmp_path / "mutants" / "mutmut-cicd-stats.json").write_text(
        '{"killed": 0, "survived": 0, "no_coverage": 0, "timeout": 0}'
    )
    run = FakeRun({
        "mutmut --version": (0, "mutmut, version 3.6.0"),
        "mutmut run": (1, ""),
        "mutmut export-cicd-stats": (0, ""),
        "mutmut results --all true": (0, "    subject_pkg.calc.x_clamp__mutmut_1: not checked\n"),
        "pytest -q --ignore=mutants": (1, "ERROR collecting tests/test_unrelated.py"),
    })
    with pytest.raises(RuntimeError, match="mutmut evaluated no mutants"):
        MutmutEngine(tmp_path, run=run).measure()


def test_measure_reraises_when_not_checked_is_mixed_with_classified_status(tmp_path):
    """A mix of "not checked" and real statuses means something WAS measured
    -- a real bug (e.g. a scope that only partially resolves) hides in the
    rest, so the zero-test fallback must not paper over it."""
    (tmp_path / "mutants").mkdir()
    (tmp_path / "mutants" / "mutmut-cicd-stats.json").write_text(
        '{"killed": 0, "survived": 1, "no_coverage": 0, "timeout": 0}'
    )
    run = FakeRun({
        "mutmut --version": (0, "mutmut, version 3.6.0"),
        "mutmut run": (1, ""),
        "mutmut export-cicd-stats": (0, ""),
        "mutmut results --all true": (0,
            "    subject_pkg.calc.x_clamp__mutmut_1: not checked\n"
            "    subject_pkg.calc.x_rate__mutmut_1: survived\n"),
        "pytest -q --ignore=mutants": (5, "no tests ran in 0.01s"),
    })
    with pytest.raises(RuntimeError, match="mutmut evaluated no mutants"):
        MutmutEngine(tmp_path, run=run).measure()
