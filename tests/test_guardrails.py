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


def test_assert_in_comment_or_string_rejected():
    sneaky = '```python\ndef test_a():\n    x = "assert"  # assert nothing\n    x\n```'
    with pytest.raises(GuardrailViolation, match="no assert statement"):
        extract_test_file(sneaky)


def test_no_assert_message_is_exact():
    # a substring match ("no assert statement") would still pass if the wording
    # grew stray characters; pin the exact string shown to the operator/log.
    with pytest.raises(GuardrailViolation) as exc_info:
        extract_test_file("```python\ndef test_a():\n    pass\n```")
    assert str(exc_info.value) == "no assert statement in generated test file"


def test_extract_strips_only_leading_trailing_newlines_not_all_whitespace():
    # a leading/trailing space is not a newline and must survive extraction
    model_output = "```python\n \nassert True\n```"
    content = extract_test_file(model_output)
    assert content == " \nassert True"


def test_extract_strip_cutset_is_the_newline_character_only():
    # a literal "X" on either edge must NOT be stripped -- only "\n" is in the cutset
    model_output = "```python\nX\nassert True\nX\n```"
    content = extract_test_file(model_output)
    assert content == "X\nassert True\nX"


def test_invalid_python_rejected():
    broken = "```python\ndef test_a(:\n    assert True\n```"
    with pytest.raises(GuardrailViolation, match="not valid python"):
        extract_test_file(broken)


def test_filename_prefix():
    assert test_filename(2, "loop") == "crucible_r2_loop_test.py"


def test_validate_passes_when_green_twice(tmp_path):
    calls = []

    def fake_run(cwd, test_paths=None, timeout=300):
        calls.append((cwd, test_paths))
        return TestRunResult(True, 0, "ok")

    validate_new_tests(tmp_path, "tests/crucible_r1_loop_test.py", fake_run)
    # flake check = run twice, and BOTH runs must be scoped to exactly the new test
    # file -- not the whole cwd (test_paths=None) and not omitted.
    assert calls == [
        (tmp_path, ["tests/crucible_r1_loop_test.py"]),
        (tmp_path, ["tests/crucible_r1_loop_test.py"]),
    ]


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


def test_validate_invalid_message_shows_last_2000_chars_of_output(tmp_path):
    # 6000 chars: deliberately NOT double the 2000-char window, so a sign flip
    # (output[+2000:] instead of output[-2000:]) can't coincidentally select the
    # same substring the way it would at exactly 4000 chars.
    long_output = "".join(f"{i:04d}" for i in range(1500))  # 6000 chars
    expected_tail = long_output[-2000:]  # independent slice, computed here, not via the code

    def fake_run(cwd, test_paths=None, timeout=300):
        return TestRunResult(False, 1, long_output)

    with pytest.raises(GuardrailViolation) as exc_info:
        validate_new_tests(tmp_path, "tests/crucible_r1_loop_test.py", fake_run)
    assert str(exc_info.value) == f"invalid: fails on pristine code\n{expected_tail}"


def test_validate_flaky_message_shows_last_2000_chars_of_second_output(tmp_path):
    long_output = "".join(f"{i:04d}" for i in range(1500))  # 6000 chars, see note above
    expected_tail = long_output[-2000:]
    results = [TestRunResult(True, 0, "ok"), TestRunResult(False, 1, long_output)]

    def fake_run(cwd, test_paths=None, timeout=300):
        return results.pop(0)

    with pytest.raises(GuardrailViolation) as exc_info:
        validate_new_tests(tmp_path, "tests/crucible_r1_loop_test.py", fake_run)
    assert str(exc_info.value) == f"flaky: passed once then failed\n{expected_tail}"


def test_add_only_accepts_expected_untracked():
    assert_add_only("?? tests/crucible_r1_loop_test.py\n", ["tests/crucible_r1_loop_test.py"])


def test_add_only_rejects_source_modification():
    status = " M subject_pkg/calc.py\n?? tests/crucible_r1_loop_test.py\n"
    with pytest.raises(GuardrailViolation, match="add-only"):
        assert_add_only(status, ["tests/crucible_r1_loop_test.py"])


def test_add_only_rejects_unexpected_new_file():
    with pytest.raises(GuardrailViolation, match="add-only"):
        assert_add_only("?? sneaky.py\n", ["tests/crucible_r1_loop_test.py"])


def test_add_only_empty_or_none_status_does_not_raise():
    # "" or None must behave as "nothing changed" (zero lines), not as some fallback
    # status text that gets parsed as a bogus git-status line.
    assert assert_add_only("", ["tests/crucible_r1_loop_test.py"]) is None
    assert assert_add_only(None, ["tests/crucible_r1_loop_test.py"]) is None


def test_add_only_blank_line_is_skipped_not_a_loop_stop():
    # a blank line must be skipped so later lines are still checked, not treated
    # as an early end-of-status marker.
    status = "\n M unexpected_file.py\n"
    with pytest.raises(GuardrailViolation, match="add-only"):
        assert_add_only(status, [])


def test_add_only_allowed_file_does_not_short_circuit_later_lines():
    # an allowed "??" line must not stop line-by-line scanning; a violation on a
    # later line must still be caught.
    status = "?? tests/crucible_r1_loop_test.py\n M some_other_file.py\n"
    with pytest.raises(GuardrailViolation, match="add-only"):
        assert_add_only(status, ["tests/crucible_r1_loop_test.py"])
