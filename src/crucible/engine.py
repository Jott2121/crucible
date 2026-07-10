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
from oracle_gate.survivors import parse_results, undetected


class ScopeError(RuntimeError):
    """The subject clone has no pyproject.toml to carry [tool.mutmut] scope."""


@dataclass(frozen=True)
class MutationOutcome:
    counts: dict
    survivors: list[str]
    all_mutants: int


class MutmutEngine:
    def __init__(self, cwd, run=subprocess.run):
        self.cwd = Path(cwd)
        self.run = run

    def measure(self) -> MutationOutcome:
        counts, results_text = run_mutation(self.cwd, run=self.run)
        mutants = parse_results(results_text)
        return MutationOutcome(
            counts=counts,
            survivors=[m.id for m in undetected(mutants)],
            all_mutants=len(mutants),
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


def write_scope(pyproject_path: Path, source_paths: list[str]) -> None:
    pyproject_path = Path(pyproject_path)
    if not pyproject_path.exists():
        raise ScopeError(f"{pyproject_path} does not exist; cannot scope mutmut")
    paths = ", ".join(f'"{p}"' for p in source_paths)
    table = f'[tool.mutmut]\nsource_paths = [{paths}]\n'
    text = pyproject_path.read_text()
    if _MUTMUT_TABLE.search(text):
        text = _MUTMUT_TABLE.sub(table, text)
    else:
        text = text.rstrip() + "\n\n" + table
    pyproject_path.write_text(text)
