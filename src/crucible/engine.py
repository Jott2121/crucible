"""Mutation engine seam. mutmut today; the interface is the contract, so another engine
(Cosmic Ray) can slot in later without touching the loop. All heavy lifting delegates to
oracle-gate's verified runner/parsers — crucible never parses mutmut output itself.

Scope note: mutmut reads its scope ONLY from [tool.mutmut] source_paths in the working
directory's pyproject. oracle-gate (a verifier) refuses to touch that config; crucible (a
generator operating on a disposable CLONE) sets it deliberately via write_scope().
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from oracle_gate.runner import run_mutation
from oracle_gate.survivors import UnclassifiedStatus, parse_results, undetected


class ScopeError(RuntimeError):
    """The subject clone has no pyproject.toml to carry [tool.mutmut] scope."""


class SandboxStatsFailure(RuntimeError):
    """mutmut's own stats phase failed inside its mutants/ sandbox for a reason
    OTHER than "no tests exist anywhere" (that case, `runner returned 5`, is the
    legitimate empty-suite baseline `_zero_test_baseline` already handles).

    This is the silent-plausible-zero bug: a generated test can pass validity
    (it collects and passes when run directly against the pristine clone --
    `SubjectEnv.validate`'s pristine-twice check, OUTSIDE mutmut's sandbox) and
    still crash the instant mutmut wraps the module inside mutants/ -- e.g. the
    test asserts a directory `also_copy` never carried in, or mutmut's own
    trampoline rejects a package-qualified import (`Failed trampoline hit`).
    mutmut then prints "failed to collect stats. runner returned <N>" (N != 5)
    or aborts early with "Stopping after <N> failures", and reports every
    mutant `not checked`. `_zero_test_baseline`'s own confirmatory pytest run
    passes fine because it runs on the pristine tree, never through mutmut's
    trampoline, so it cannot tell a real empty-coverage baseline apart from
    this sandbox-only crash -- it would otherwise launder the crash into a
    false all-survived zero. This exception exists so the caller rejects the
    round instead of ever recording that plausible zero."""


@dataclass(frozen=True)
class MutationOutcome:
    counts: dict
    survivors: list[str]
    all_mutants: int


# exit 5 = "no tests collected anywhere" -- the one `runner returned` code that
# IS the legitimate empty-suite baseline (protocol §3: idna/packaging's
# strip_tests subjects), left for `_zero_test_baseline` to classify. Any other
# code, or an early "Stopping after N failures" abort, means pytest itself
# broke or failed INSIDE the sandbox -- a real crash, not empty coverage.
_LEGITIMATE_EMPTY_SUITE_RUNNER_CODE = 5
_STATS_FAILURE_RE = re.compile(r"failed to collect stats\.\s*runner returned (\d+)", re.I)
_STOPPING_AFTER_RE = re.compile(r"stopping after \d+ failures?", re.I)


def _sandbox_stats_failure_tail(stdout: str, lines: int = 40) -> str | None:
    """None when a captured `mutmut run` invocation's stdout+stderr shows no
    sandbox-only failure; otherwise the last `lines` lines of it, for the
    exception message (naming the failing test output tail, per spec)."""
    if not stdout:
        return None
    match = _STATS_FAILURE_RE.search(stdout)
    if match and int(match.group(1)) != _LEGITIMATE_EMPTY_SUITE_RUNNER_CODE:
        return "\n".join(stdout.splitlines()[-lines:])
    if _STOPPING_AFTER_RE.search(stdout):
        return "\n".join(stdout.splitlines()[-lines:])
    return None


class MeasureTimeout(RuntimeError):
    """`mutmut run` exceeded MUTMUT_RUN_TIMEOUT_S. Without this bound a
    measure can hang forever with no receipt trace: a generated test that
    spawns its own process pool (e.g. sklearn/joblib's loky workers) can
    deadlock inside mutmut's already-forked workers -- observed live on
    attrition-risk-ml 2026-07-10, all workers 0% CPU for 68+ minutes. The
    bound converts an unbounded silent hang into the established loud
    crashed-cell posture. subprocess kills only the direct child on timeout,
    so deadlocked orphan workers may need manual cleanup (named here so the
    operator knows to look)."""


# Generous: the slowest legitimate measure observed (attrition-risk-ml, 255
# mutants, sklearn-training tests) is ~30 minutes. A measure past this bound
# has always meant a hang, never slow progress.
MUTMUT_RUN_TIMEOUT_S = 3600


class _RunTee:
    """Wraps a `run` callable, capturing the stdout+stderr of the `mutmut run`
    invocation specifically -- the one call in `oracle_gate.runner.run_mutation`
    whose output can show a sandbox stats-phase failure, which the cicd-stats
    JSON and `mutmut results` text (the only things run_mutation returns) do
    not otherwise surface: run_mutation checks `mutmut run`'s exit code is
    non-fatal (survivors alone make it non-zero) and then discards its stdout.

    Also bounds that same invocation with MUTMUT_RUN_TIMEOUT_S (see
    MeasureTimeout); every other command through this tee (mutmut show,
    pytest) is left untouched -- run_tests carries its own timeout."""

    def __init__(self, run):
        self._run = run
        self.run_stdout = ""

    def __call__(self, cmd, *args, **kwargs):
        is_mutmut_run = list(cmd[-2:]) == ["mutmut", "run"]
        if is_mutmut_run:
            kwargs.setdefault("timeout", MUTMUT_RUN_TIMEOUT_S)
        try:
            proc = self._run(cmd, *args, **kwargs)
        except subprocess.TimeoutExpired as exc:
            raise MeasureTimeout(
                f"`mutmut run` produced no result within {kwargs.get('timeout')}s "
                "-- treated as a hang (a generated test spawning its own process "
                "pool can deadlock inside mutmut's forked workers), never as a "
                "measurement. Orphaned mutmut worker processes may remain and "
                "need manual cleanup."
            ) from exc
        if is_mutmut_run:
            self.run_stdout = (getattr(proc, "stdout", "") or "") + (getattr(proc, "stderr", "") or "")
        return proc


class MutmutEngine:
    def __init__(self, cwd, run=subprocess.run):
        self.cwd = Path(cwd)
        self.run = run

    def measure(self) -> MutationOutcome:
        tee = _RunTee(self.run)
        counts, results_text = run_mutation(self.cwd, run=tee)
        mutants = parse_results(results_text)
        try:
            survivors = [m.id for m in undetected(mutants)]
        except UnclassifiedStatus as exc:
            failure_tail = _sandbox_stats_failure_tail(tee.run_stdout)
            if failure_tail is not None:
                raise SandboxStatsFailure(
                    f"{exc}; mutmut's stats phase failed inside its own mutants/ "
                    "sandbox (not a legitimate empty-suite baseline) -- likely a "
                    "generated test that passes on the pristine module but crashes "
                    "once mutmut wraps it (a directory also_copy doesn't carry in, "
                    "a trampoline import mismatch, etc). Tail of `mutmut run` "
                    f"output:\n{failure_tail}"
                ) from exc
            zero_test_outcome = self._zero_test_baseline(mutants)
            if zero_test_outcome is not None:
                return zero_test_outcome
            raise RuntimeError(
                f"{exc}; mutmut evaluated no mutants — usually a broken [tool.mutmut] "
                "scope (missing also_copy?) or a collection error inside the mutants "
                "sandbox; run `python -m mutmut run` in the subject to see the "
                "underlying failure"
            ) from exc
        return MutationOutcome(
            counts=counts,
            survivors=survivors,
            all_mutants=len(mutants),
        )

    def _zero_test_baseline(self, mutants) -> MutationOutcome | None:
        """Every generated mutant sits at status "not checked" in exactly two
        legitimate cases, both amounting to the same mechanically provable
        fact -- nothing exercises the mutated module, so nothing could have
        killed a mutant:

        (a) the subject has literally zero test files anywhere. mutmut's
            baseline "Running stats" phase is a bare pytest run over the whole
            subject, and it hard-fails -- "failed to collect stats. runner
            returned 5" -- rather than reporting 0% coverage, when pytest
            itself finds nothing to collect. That is exactly the pristine
            state a stripped third-party subject starts a cell in (protocol
            §3: "scored against a genuinely empty starting suite").
        (b) the subject's existing test suite collects and passes cleanly
            (exit 0) but genuinely never executes the mutated module (a
            module with zero test coverage, e.g. attrition-risk-ml's train.py
            per protocol §3.1's pre-declared "degenerate maximal-headroom
            false-pass case"). mutmut's per-mutant "no tests" status already
            gets this exact treatment (oracle_gate.survivors.UNDETECTED) when
            SOME but not all mutants in a file lack coverage; mutmut's own
            global sanity check ("Stopping early, because we could not find
            any test case for any mutant") just aborts before classifying
            anything at the 100%-uncovered boundary instead of reporting
            "no tests" for every mutant. This extends the same semantics to
            that boundary rather than inventing a new one.

        Any OTHER cause of "not checked" (a real [tool.mutmut] scope bug: a
        missing also_copy entry, an unrelated test file failing to collect,
        etc.) must still fail loud, so this only fires when (1) EVERY mutant
        is "not checked" -- a partial mix means something real was measured
        and a real bug is hiding in the rest -- and (2) a bare, unscoped
        `pytest -q` in the subject confirms either (a) or (b) above (exit
        code 5 or 0), never a genuine failure or collection error (exit code
        1/2/3/4). Returns None when either condition fails, so the caller
        raises the original loud error. This cannot mechanically distinguish
        case (b) from a genuine scope bug that happens to leave an unrelated
        green suite in place (e.g. source_paths pointing at the wrong file);
        `experiments/validate_scopes.py` is the second line of defense for
        that -- it also checks the mutant COUNT against the pre-registered
        smoke figure, which a wrong-file scope would also disturb.
        """
        if not mutants or any(m.status != "not checked" for m in mutants):
            return None
        # --ignore=mutants: by this point mutmut has already generated its own
        # mutants/ tree (a copy of source_paths + also_copy, including any
        # also_copy'd test files this subject keeps). An unscoped `pytest -q`
        # from the subject root would otherwise collect the SAME test module
        # basename from both the real tests/ dir and its mutants/ mirror and
        # error out on pytest's "import file mismatch" -- a collision this
        # confirmatory check causes by running after mutation generation, not
        # a real failure of the subject's own suite.
        try:
            pristine = self.run(
                [sys.executable, "-m", "pytest", "-q", "--ignore=mutants"],
                cwd=str(self.cwd), capture_output=True, text=True, timeout=300,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "pristine suite timed out (300s) during zero-baseline confirmation"
            ) from exc
        if pristine.returncode not in (0, 5):
            return None
        ids = [m.id for m in mutants]
        return MutationOutcome(
            counts={
                "killed": 0, "survived": len(ids), "total": len(ids),
                "no_tests": 0, "skipped": 0, "suspicious": 0, "timeout": 0,
                "check_was_interrupted_by_user": 0, "segfault": 0,
            },
            survivors=ids,
            all_mutants=len(ids),
        )

    def survivor_diff(self, mutant_id: str) -> str:
        proc = self.run(
            [sys.executable, "-m", "mutmut", "show", mutant_id],
            cwd=str(self.cwd), capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"`mutmut show {mutant_id}` failed: {proc.stderr}")
        return proc.stdout


_MUTMUT_TABLE = re.compile(r"^\[tool\.mutmut\]\n(?:(?!^\[).)*", re.M | re.S)


def write_scope(pyproject_path: Path, source_paths: list[str],
                 also_copy: list[str] | None = None,
                 pytest_args: list[str] | None = None,
                 create_if_missing: bool = False) -> None:
    pyproject_path = Path(pyproject_path)
    if not pyproject_path.exists():
        if not create_if_missing:
            raise ScopeError(f"{pyproject_path} does not exist; cannot scope mutmut")
        # A subject clone with no packaging metadata at all (e.g. a plain
        # source tree, no pyproject.toml/setup.cfg) has nowhere for mutmut to
        # read [tool.mutmut] from. crucible operates on a disposable clone, so
        # it is safe to create a minimal file carrying ONLY the mutmut scope
        # table -- never real project metadata, which crucible has no basis
        # to invent.
        pyproject_path.write_text("# created by crucible preflight — mutmut scope only\n")
    paths = ", ".join(f'"{p}"' for p in source_paths)
    lines = ["[tool.mutmut]", f"source_paths = [{paths}]"]
    if also_copy:
        ac = ", ".join(f'"{p}"' for p in also_copy)
        lines.append(f"also_copy = [{ac}]")
    if pytest_args:
        pa = ", ".join(f'"{p}"' for p in pytest_args)
        lines.append(f"pytest_add_cli_args_test_selection = [{pa}]")
    table = "\n".join(lines) + "\n"
    text = pyproject_path.read_text()
    if _MUTMUT_TABLE.search(text):
        text = _MUTMUT_TABLE.sub(table, text)
    else:
        text = text.rstrip() + "\n\n" + table
    pyproject_path.write_text(text)
