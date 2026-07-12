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


def test_run_tests_ignores_mutants_dir(tmp_path):
    """Finding E: preflight's pristine-suite check runs pytest at the repo
    root; a leftover mutants/ dir (the canary probe's or a manual mutmut
    run's residue, containing copied tests/test_*.py) makes pytest die on
    import-file-mismatch collection errors and falsely reports 'red on
    pristine code'. run_tests must carry --ignore=mutants, the same dodge
    the canary's own pristine check (scope.py) and engine's
    _zero_test_baseline already use. Explicit test_paths callers
    (validate/salvage) are unaffected: their paths live under tests/,
    outside mutants/."""
    captured = {}

    def run(cmd, cwd=None, capture_output=True, text=True, timeout=None):
        captured["cmd"] = cmd

        class P:
            returncode, stdout, stderr = 0, "ok", ""
        return P()

    run_tests("/subject", run=run)
    assert "--ignore=mutants" in captured["cmd"]
    # and with explicit test paths, the flag rides along without displacing them
    run_tests("/subject", test_paths=["tests/crucible_a_test.py"], run=run)
    assert "--ignore=mutants" in captured["cmd"]
    assert "tests/crucible_a_test.py" in captured["cmd"]


def test_timeout_is_a_failure_not_a_crash():
    def run(cmd, cwd=None, capture_output=True, text=True, timeout=None):
        raise subprocess.TimeoutExpired(cmd, timeout)
    r = run_tests("/subject", timeout=5, run=run)
    assert r.passed is False and r.returncode == -1 and "TIMEOUT" in r.output
