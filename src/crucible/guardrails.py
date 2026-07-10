"""The anti-gaming layer. Agents make tests "pass" by weakening things (Kent Beck's
observation; our standard's failure-mode list). Crucible never trusts the model's output
shape or conduct — every rule here is a hard check, not a prompt instruction.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path


class GuardrailViolation(RuntimeError):
    """Model output broke a hard rule; the round rejects it (never a crash)."""


_PY_BLOCK = re.compile(r"```python\n(.*?)```", re.S)


def extract_test_file(model_output: str) -> str:
    blocks = _PY_BLOCK.findall(model_output or "")
    if len(blocks) != 1:
        raise GuardrailViolation(
            f"expected exactly one fenced python block, found {len(blocks)}"
        )
    content = blocks[0].strip("\n")
    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        raise GuardrailViolation(f"generated test file is not valid python: {exc}") from None
    if not any(isinstance(node, ast.Assert) for node in ast.walk(tree)):
        raise GuardrailViolation("no assert statement in generated test file")
    return content


def test_filename(round_no: int, arm: str) -> str:
    return f"crucible_r{round_no}_{arm}_test.py"


test_filename.__test__ = False  # not a pytest test; name collides with test_* discovery


def validate_new_tests(cwd, test_path, run_tests_fn) -> None:
    """New tests must pass on PRISTINE code (else they encode a wrong oracle), twice
    (else they're flaky and their kills are noise). Kept for compatibility; SubjectEnv
    calls salvage_new_tests instead (v3: per-test salvage rather than all-or-nothing)."""
    first = run_tests_fn(cwd, test_paths=[str(test_path)])
    if not first.passed:
        raise GuardrailViolation(f"invalid: fails on pristine code\n{first.output[-2000:]}")
    second = run_tests_fn(cwd, test_paths=[str(test_path)])
    if not second.passed:
        raise GuardrailViolation(f"flaky: passed once then failed\n{second.output[-2000:]}")


# pytest's short-test-summary-info section prints one of two line shapes depending on
# verbosity: "FAILED path::name - reason" (the default, and what -rf forces even under
# addopts that might otherwise suppress it) or, in some verbose (-v) progress output,
# "path::name FAILED   [ 50%]". Both are matched so this stays robust either way.
_FAILED_PREFIX = re.compile(r"^FAILED\s+(\S+)")
_FAILED_SUFFIX = re.compile(r"^(\S+)\s+FAILED\b")


def _parse_failed_test_names(output: str) -> set[str]:
    names = set()
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        match = _FAILED_PREFIX.match(line) or _FAILED_SUFFIX.match(line)
        if not match:
            continue
        spec = match.group(1)
        name = spec.split("::")[-1].split("[")[0]  # drop path::, keep func; strip param id
        if name:
            names.add(name)
    return names


def salvage_new_tests(cwd, test_path, run_tests_fn, read_file, write_file) -> list[str]:
    """Per-test salvage of the validity gate (v3 amendment): a test that fails on the
    pinned pristine subject encodes a wrong oracle for THAT test, not the whole file.
    Mutation-testing convention treats the pinned subject as ground truth at baseline,
    so a pristine-failing test is dropped and logged rather than rejecting 12 good
    tests alongside 1 bad one.

    Green on the first pristine run -> flake-check (second run) -> return [] (nothing
    dropped). Red -> parse the failed test names out of the pytest summary, remove
    exactly those FunctionDef nodes from the file (ast parse/unparse), re-run: the
    pruned file must pass, then flake-check again. Returns the names actually dropped.

    read_file(cwd, test_path) -> str and write_file(cwd, test_path, content) -> None
    are injected so this stays unit-testable without touching a real filesystem; the
    real env supplies IO bound to the subject clone.
    """
    first = run_tests_fn(cwd, test_paths=[str(test_path)])
    if first.passed:
        second = run_tests_fn(cwd, test_paths=[str(test_path)])
        if not second.passed:
            raise GuardrailViolation(f"flaky: passed once then failed\n{second.output[-2000:]}")
        return []

    failed_names = _parse_failed_test_names(first.output)
    if not failed_names:
        raise GuardrailViolation(f"invalid: fails on pristine code\n{first.output[-2000:]}")

    source = read_file(cwd, test_path)
    tree = ast.parse(source)
    top_level_tests = {
        node.name for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
    }
    missing = failed_names - top_level_tests
    if missing:
        raise GuardrailViolation(
            f"salvage failed: could not locate failed test(s) {sorted(missing)} "
            f"as top-level functions in {test_path}"
        )

    tree.body = [
        node for node in tree.body
        if not (isinstance(node, ast.FunctionDef) and node.name in failed_names)
    ]
    remaining = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
    ]
    if not remaining:
        raise GuardrailViolation(
            f"invalid: every generated test failed on pristine code "
            f"(dropped {sorted(failed_names)}, nothing left to salvage)"
        )

    pruned = ast.unparse(ast.fix_missing_locations(tree))
    write_file(cwd, test_path, pruned + "\n")

    rerun = run_tests_fn(cwd, test_paths=[str(test_path)])
    if not rerun.passed:
        raise GuardrailViolation(
            f"invalid: pruned file still fails on pristine code\n{rerun.output[-2000:]}"
        )
    flake = run_tests_fn(cwd, test_paths=[str(test_path)])
    if not flake.passed:
        raise GuardrailViolation(
            f"flaky: passed once then failed after salvage\n{flake.output[-2000:]}"
        )
    return sorted(failed_names)


def assert_add_only(git_status_output: str, allowed_new) -> None:
    allowed = {str(Path(p)) for p in allowed_new}
    for line in (git_status_output or "").splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip()
        if code == "??" and str(Path(path)) in allowed:
            continue
        raise GuardrailViolation(f"add-only violated: unexpected change {line.strip()!r}")
