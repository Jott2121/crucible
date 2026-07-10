import pytest

from crucible.guardrails import (
    GuardrailViolation,
    assert_add_only,
    extract_test_file,
    test_filename,
    validate_new_tests,
)
from crucible.runner import TestRunResult


def test_extracts_single_python_block():
    out = "Here you go:\n```python\ndef test_a():\n    assert 1 == 1\n```\nDone."
    assert extract_test_file(out) == "def test_a():\n    assert 1 == 1"


def test_zero_blocks_rejected():
    with pytest.raises(GuardrailViolation, match="one fenced python block"):
        extract_test_file("no code here")


def test_two_blocks_rejected():
    two = "```python\nassert True\n```\n```python\nassert True\n```"
    with pytest.raises(GuardrailViolation, match="one fenced python block"):
        extract_test_file(two)


def test_no_assert_rejected():
    with pytest.raises(GuardrailViolation, match="no assert"):
        extract_test_file("```python\ndef test_a():\n    pass\n```")


def test_filename_prefix():
    assert test_filename(2, "loop") == "crucible_r2_loop_test.py"


def test_validate_passes_when_green_twice(tmp_path):
    calls = []

    def fake_run(cwd, test_paths=None, timeout=300):
        calls.append(test_paths)
        return TestRunResult(True, 0, "ok")

    validate_new_tests(tmp_path, "tests/crucible_r1_loop_test.py", fake_run)
    assert len(calls) == 2  # flake check = run twice


def test_validate_rejects_red_on_pristine(tmp_path):
    def fake_run(cwd, test_paths=None, timeout=300):
        return TestRunResult(False, 1, "1 failed")

    with pytest.raises(GuardrailViolation, match="invalid"):
        validate_new_tests(tmp_path, "tests/crucible_r1_loop_test.py", fake_run)


def test_validate_rejects_flaky(tmp_path):
    results = [TestRunResult(True, 0, "ok"), TestRunResult(False, 1, "flaked")]

    def fake_run(cwd, test_paths=None, timeout=300):
        return results.pop(0)

    with pytest.raises(GuardrailViolation, match="flaky"):
        validate_new_tests(tmp_path, "tests/crucible_r1_loop_test.py", fake_run)


def test_add_only_accepts_expected_untracked():
    assert_add_only("?? tests/crucible_r1_loop_test.py\n", ["tests/crucible_r1_loop_test.py"])


def test_add_only_rejects_source_modification():
    status = " M subject_pkg/calc.py\n?? tests/crucible_r1_loop_test.py\n"
    with pytest.raises(GuardrailViolation, match="add-only"):
        assert_add_only(status, ["tests/crucible_r1_loop_test.py"])


def test_add_only_rejects_unexpected_new_file():
    with pytest.raises(GuardrailViolation, match="add-only"):
        assert_add_only("?? sneaky.py\n", ["tests/crucible_r1_loop_test.py"])
