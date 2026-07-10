import subprocess

from crucible.runner import TestRunResult, run_tests


def _fake(rc, out):
    def run(cmd, cwd=None, capture_output=True, text=True, timeout=None):
        class P:
            returncode, stdout, stderr = rc, out, ""
        return P()
    return run


def test_green_suite():
    r = run_tests("/subject", run=_fake(0, "3 passed"))
    assert r == TestRunResult(passed=True, returncode=0, output="3 passed")


def test_red_suite():
    r = run_tests("/subject", test_paths=["tests/crucible_a_test.py"], run=_fake(1, "1 failed"))
    assert r.passed is False and r.returncode == 1


def test_timeout_is_a_failure_not_a_crash():
    def run(cmd, cwd=None, capture_output=True, text=True, timeout=None):
        raise subprocess.TimeoutExpired(cmd, timeout)
    r = run_tests("/subject", timeout=5, run=run)
    assert r.passed is False and r.returncode == -1 and "TIMEOUT" in r.output
