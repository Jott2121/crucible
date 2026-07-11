import pytest

from crucible.guardrails import (
    GuardrailViolation,
    assert_add_only,
    extract_test_file,
    salvage_new_tests,
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


# --- salvage_new_tests: per-test salvage (v3 amendment) ---
#
# Mutation-testing convention treats the pinned subject as ground truth at baseline:
# a test that fails on pristine code encodes a wrong oracle for THIS subject and is
# droppable, not fatal to the whole file. read_file/write_file are injected so this
# stays unit-testable without touching a real filesystem.

SOURCE_THREE_TESTS = (
    "def test_a():\n    assert True\n\n\n"
    "def test_b():\n    assert False\n\n\n"
    "def test_c():\n    assert True\n"
)

SOURCE_TWO_TESTS = "def test_a():\n    assert False\n\n\ndef test_b():\n    assert False\n"

SOURCE_ONE_TEST = "def test_a():\n    assert True\n"

SOURCE_TWO_TESTS_ONE_BAD = "def test_a():\n    assert True\n\n\ndef test_b():\n    assert False\n"


def _no_read_write():
    def fake_read(cwd, path):
        raise AssertionError("must not read the file on a green pristine run")

    def fake_write(cwd, path, content):
        raise AssertionError("must not write the file on a green pristine run")

    return fake_read, fake_write


def test_salvage_green_file_flake_checks_and_returns_empty_list():
    calls = []

    def fake_run(cwd, test_paths=None, timeout=300):
        calls.append((cwd, test_paths))
        return TestRunResult(True, 0, "ok")

    fake_read, fake_write = _no_read_write()
    dropped = salvage_new_tests(
        "/subject", "tests/crucible_r0_x_test.py", fake_run, fake_read, fake_write
    )
    assert dropped == []
    # flake check = run twice, both scoped to exactly the new test file
    assert calls == [
        ("/subject", ["tests/crucible_r0_x_test.py"]),
        ("/subject", ["tests/crucible_r0_x_test.py"]),
    ]


def test_salvage_green_then_red_is_flaky():
    results = [TestRunResult(True, 0, "ok"), TestRunResult(False, 1, "flaked")]

    def fake_run(cwd, test_paths=None, timeout=300):
        return results.pop(0)

    fake_read, fake_write = _no_read_write()
    with pytest.raises(GuardrailViolation, match="flaky"):
        salvage_new_tests("/subject", "tests/x_test.py", fake_run, fake_read, fake_write)


def test_salvage_drops_exactly_the_failing_test_and_reruns_green():
    run_outputs = [
        TestRunResult(
            False, 1,
            "FAILED tests/crucible_r0_x_test.py::test_b - assert False\n1 failed, 2 passed",
        ),
        TestRunResult(True, 0, "2 passed"),
        TestRunResult(True, 0, "2 passed"),
    ]
    calls = []

    def fake_run(cwd, test_paths=None, timeout=300):
        calls.append(test_paths)
        return run_outputs.pop(0)

    def fake_read(cwd, path):
        assert path == "tests/crucible_r0_x_test.py"
        return SOURCE_THREE_TESTS

    written = {}

    def fake_write(cwd, path, content):
        written["path"] = path
        written["content"] = content

    dropped = salvage_new_tests(
        "/subject", "tests/crucible_r0_x_test.py", fake_run, fake_read, fake_write
    )
    assert dropped == ["test_b"]
    assert "def test_b" not in written["content"]
    assert "def test_a" in written["content"] and "def test_c" in written["content"]
    assert written["path"] == "tests/crucible_r0_x_test.py"
    assert len(calls) == 3  # 1 pristine run + 2 post-prune (green + flake check)


def test_salvage_parses_suffix_style_failed_lines():
    # some pytest verbose output styles print "path::name FAILED" rather than
    # "FAILED path::name"; the parser must be robust to both.
    run_outputs = [
        TestRunResult(False, 1, "tests/x_test.py::test_b FAILED             [ 50%]\n1 failed, 1 passed"),
        TestRunResult(True, 0, "1 passed"),
        TestRunResult(True, 0, "1 passed"),
    ]

    def fake_run(cwd, test_paths=None, timeout=300):
        return run_outputs.pop(0)

    def fake_read(cwd, path):
        return SOURCE_TWO_TESTS_ONE_BAD

    written = {}

    def fake_write(cwd, path, content):
        written["content"] = content

    dropped = salvage_new_tests("/subject", "tests/x_test.py", fake_run, fake_read, fake_write)
    assert dropped == ["test_b"]
    assert "def test_b" not in written["content"]
    assert "def test_a" in written["content"]


def test_salvage_raises_when_all_tests_fail_on_pristine():
    def fake_run(cwd, test_paths=None, timeout=300):
        return TestRunResult(
            False, 1, "FAILED tests/x.py::test_a\nFAILED tests/x.py::test_b\n2 failed"
        )

    def fake_read(cwd, path):
        return SOURCE_TWO_TESTS

    def fake_write(cwd, path, content):
        raise AssertionError("must not write a file with zero surviving tests")

    with pytest.raises(GuardrailViolation, match="invalid"):
        salvage_new_tests("/subject", "tests/x.py", fake_run, fake_read, fake_write)


def test_salvage_raises_when_no_failed_names_can_be_parsed():
    # red output that names no specific test: nothing is droppable, so the whole
    # file is invalid (identical to validate_new_tests's prior behavior).
    def fake_run(cwd, test_paths=None, timeout=300):
        return TestRunResult(False, 1, "collection error: ImportError: no module named x")

    def fake_read(cwd, path):
        raise AssertionError("must not read the file when no failed test names were found")

    def fake_write(cwd, path, content):
        raise AssertionError("must not write when no failed test names were found")

    with pytest.raises(GuardrailViolation, match="invalid"):
        salvage_new_tests("/subject", "tests/x.py", fake_run, fake_read, fake_write)


def test_salvage_raises_when_failed_name_not_found_in_ast():
    def fake_run(cwd, test_paths=None, timeout=300):
        return TestRunResult(False, 1, "FAILED tests/x.py::test_nonexistent\n1 failed")

    def fake_read(cwd, path):
        return SOURCE_ONE_TEST

    def fake_write(cwd, path, content):
        raise AssertionError("must not write before every failed name resolves in the AST")

    with pytest.raises(GuardrailViolation, match="salvage failed"):
        salvage_new_tests("/subject", "tests/x.py", fake_run, fake_read, fake_write)


def test_salvage_raises_when_pruned_file_still_fails():
    run_outputs = [
        TestRunResult(False, 1, "FAILED tests/x.py::test_b\n1 failed, 1 passed"),
        TestRunResult(False, 1, "still red somehow"),
    ]

    def fake_run(cwd, test_paths=None, timeout=300):
        return run_outputs.pop(0)

    def fake_read(cwd, path):
        return SOURCE_TWO_TESTS_ONE_BAD

    def fake_write(cwd, path, content):
        pass

    with pytest.raises(GuardrailViolation, match="invalid"):
        salvage_new_tests("/subject", "tests/x.py", fake_run, fake_read, fake_write)


def test_salvage_raises_flaky_after_prune():
    run_outputs = [
        TestRunResult(False, 1, "FAILED tests/x.py::test_b\n1 failed, 1 passed"),
        TestRunResult(True, 0, "1 passed"),
        TestRunResult(False, 1, "flaked"),
    ]

    def fake_run(cwd, test_paths=None, timeout=300):
        return run_outputs.pop(0)

    def fake_read(cwd, path):
        return SOURCE_TWO_TESTS_ONE_BAD

    def fake_write(cwd, path, content):
        pass

    with pytest.raises(GuardrailViolation, match="flaky"):
        salvage_new_tests("/subject", "tests/x.py", fake_run, fake_read, fake_write)
