"""Scope setup for a subject repo: detect layout, write [tool.mutmut], flag
sandbox-hazard test files. Mechanizes the lessons the experiment learned the
hard way: exclude-form pytest_args only (v6 -- an include-list silently
stops collecting freshly generated tests), a src-layout conftest shim (v7 --
mutmut's trampoline rejects src.-qualified imports). Heuristics never guess:
what detect() cannot prove lands in notes, and the canary probe (crucible
scope's second half) is the mechanical gate before any model spend."""
from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

from crucible.engine import write_scope

SRC_SHIM = 'import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))\n'


@dataclass(frozen=True)
class ScopePlan:
    module: str
    also_copy: list[str]
    pytest_args: list[str]
    needs_src_shim: bool
    notes: list[str] = field(default_factory=list)


def _top_level_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def detect(subject_dir: Path, module: str) -> ScopePlan:
    subject_dir = Path(subject_dir)
    if not (subject_dir / module).is_file():
        raise FileNotFoundError(f"module not found in subject: {module}")
    top = Path(module).parts[0]
    also_copy = [top]
    needs_src_shim = top == "src"
    notes: list[str] = []
    pytest_args: list[str] = []
    tests_dir = subject_dir / "tests"
    if tests_dir.is_dir():
        for tf in sorted(tests_dir.glob("test_*.py")):
            hazards = {
                name for name in _top_level_imports(tf)
                if name != top
                and (subject_dir / name).is_dir()               # local top-level package...
                and importlib.util.find_spec(name) is None      # ...not an installed one
            }
            if hazards:
                pytest_args.append(f"--ignore=tests/{tf.name}")
                notes.append(f"tests/{tf.name} imports local package(s) "
                             f"{sorted(hazards)} absent from mutmut's sandbox")
    return ScopePlan(module=module, also_copy=also_copy, pytest_args=pytest_args,
                     needs_src_shim=needs_src_shim, notes=notes)


def apply(subject_dir: Path, plan: ScopePlan) -> None:
    subject_dir = Path(subject_dir)
    if plan.needs_src_shim:
        (subject_dir / "conftest.py").write_text(SRC_SHIM)
    write_scope(subject_dir / "pyproject.toml", [plan.module],
                also_copy=plan.also_copy,
                pytest_args=plan.pytest_args or None,
                create_if_missing=True)
