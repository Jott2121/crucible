"""Run the subject's tests in a subprocess. The only place pytest is invoked."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class TestRunResult:
    __test__ = False  # name starts with Test; tell pytest it is not a test class
    passed: bool
    returncode: int
    output: str


def run_tests(cwd, test_paths=None, timeout=300, run=subprocess.run) -> TestRunResult:
    cmd = [sys.executable, "-m", "pytest", "-q", *(test_paths or [])]
    try:
        proc = run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return TestRunResult(passed=False, returncode=-1, output=f"TIMEOUT after {timeout}s")
    return TestRunResult(
        passed=proc.returncode == 0,
        returncode=proc.returncode,
        output=(proc.stdout or "") + (proc.stderr or ""),
    )
