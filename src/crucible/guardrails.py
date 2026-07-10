"""The anti-gaming layer. Agents make tests "pass" by weakening things (Kent Beck's
observation; our standard's failure-mode list). Crucible never trusts the model's output
shape or conduct — every rule here is a hard check, not a prompt instruction.
"""
from __future__ import annotations

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
    if "assert" not in content:
        raise GuardrailViolation("no assert in generated test file")
    return content


def test_filename(round_no: int, arm: str) -> str:
    return f"crucible_r{round_no}_{arm}_test.py"


test_filename.__test__ = False  # not a pytest test; name collides with test_* discovery


def validate_new_tests(cwd, test_path, run_tests_fn) -> None:
    """New tests must pass on PRISTINE code (else they encode a wrong oracle), twice
    (else they're flaky and their kills are noise)."""
    first = run_tests_fn(cwd, test_paths=[str(test_path)])
    if not first.passed:
        raise GuardrailViolation(f"invalid: fails on pristine code\n{first.output[-2000:]}")
    second = run_tests_fn(cwd, test_paths=[str(test_path)])
    if not second.passed:
        raise GuardrailViolation(f"flaky: passed once then failed\n{second.output[-2000:]}")


def assert_add_only(git_status_output: str, allowed_new) -> None:
    allowed = {str(Path(p)) for p in allowed_new}
    for line in (git_status_output or "").splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip()
        if code == "??" and str(Path(path)) in allowed:
            continue
        raise GuardrailViolation(f"add-only violated: unexpected change {line.strip()!r}")
