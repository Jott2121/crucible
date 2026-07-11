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
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from crucible.engine import MutmutEngine, write_scope

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


@dataclass(frozen=True)
class CanaryVerdict:
    kills_before: int
    kills_after: int
    mutants: int
    passed: bool


def _public_top_level_names(path: Path) -> list[str]:
    """Public function/class/constant names bound at module level in `path`,
    in source order -- read from the PRISTINE file on disk, never from
    `dir()` of the imported module. `dir()` on a module loaded from inside
    mutmut's mutants/ sandbox is polluted with mutmut's own bookkeeping
    (a `MutantDict` type alias, a `mutants_x_<fn>__mutmut` trampoline dict,
    and each individual `x_<fn>__mutmut_N` mutant function, all as ordinary
    module attributes) -- alphabetically 'MutantDict' sorts before any
    lowercase target name, so a dir()-picked "first public name" silently
    resolves to mutmut's internal type alias instead of the target symbol,
    and can never register a kill. Reading names from the pristine source
    keeps the canary pinned to the real target regardless of sandbox noise."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return []
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and not node.name.startswith("_"):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    names.append(target.id)
    return names


# Bounded, safe smoke-call arg tuples across the common small arities (0-3
# positional params); TypeError from an arity mismatch is skipped, any OTHER
# exception (e.g. a boundary condition mutated into a ZeroDivisionError) is
# left to propagate as a genuine, mechanically real kill.
_CANARY_PROBES = [(), (0,), (1,), (0, 0), (1, 0), (0, 1), (1, 1), (-1, 1),
                   (0, 0, 0), (5, 0, 10), (-1, 0, 10), (11, 0, 10)]

_CANARY = (
    "import importlib\n"
    "mod = importlib.import_module({modname!r})\n"
    "_NAMES = {names!r}\n"
    "_PROBES = {probes!r}\n"
    "def test_crucible_canary():\n"
    "    assert _NAMES, 'module exports nothing public'\n"
    "    for name in _NAMES:\n"
    "        obj = getattr(mod, name, None)\n"
    "        assert obj is not None, name + ' missing from ' + mod.__name__\n"
    "        if not callable(obj):\n"
    "            continue\n"
    "        for args in _PROBES:\n"
    "            try:\n"
    "                obj(*args)\n"
    "            except TypeError:\n"
    "                continue\n"
    "            else:\n"
    "                break\n"
)


def canary_probe(subject_dir: Path, module: str, run=subprocess.run) -> CanaryVerdict:
    """Must-kill collection proof before any model spend (v6 lesson): write a
    canary test, prove it passes pristine BEFORE spending a single full
    mutmut measure, measure the pre-canary baseline, restore the canary, and
    require the killed count to STRICTLY increase. Proves mutmut actually
    collects a freshly written test file under this scope; the smoke-call
    over the target's public symbols (bounded, safe argument tuples; only an
    arity TypeError is swallowed) gives it a real, if narrow, chance of
    actually killing a mutant -- it does not claim deep behavioral coverage,
    the loop's generated tests supply that.

    Deliberately checks pristine validity first (a single `run` call) rather
    than measuring "before" first: a broken `run` seam must fail loud on the
    canary check itself, not three calls deep inside a full mutmut measure.
    The canary file is parked outside tests/ while "before" is measured (a
    true pre-canary baseline) and restored for "after"; both paths are
    removed in a finally, pass or fail."""
    subject_dir = Path(subject_dir)
    modname = module[:-3].replace("/", ".")
    if modname.startswith("src."):
        modname = modname[len("src."):]          # v7: bare name, never src.-qualified
    names = _public_top_level_names(subject_dir / module)
    engine = MutmutEngine(subject_dir, run=run)
    tests_dir = subject_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    canary = tests_dir / "crucible_canary_test.py"
    parked = subject_dir / ".crucible_canary_test.py.parked"
    try:
        canary.write_text(_CANARY.format(modname=modname, names=names, probes=_CANARY_PROBES))
        pristine = run([sys.executable, "-m", "pytest", "-q", str(canary), "--ignore=mutants"],
                       cwd=str(subject_dir), capture_output=True, text=True, timeout=300)
        if pristine.returncode != 0:
            raise RuntimeError(
                "canary failed on pristine code -- the probe is wrong, not the subject: "
                f"{(pristine.stdout or '')[-400:]}")
        canary.rename(parked)             # true pre-canary baseline for "before"
        before = engine.measure()
        parked.rename(canary)             # restore for "after"
        after = engine.measure()
    finally:
        canary.unlink(missing_ok=True)
        parked.unlink(missing_ok=True)
    return CanaryVerdict(
        kills_before=int(before.counts.get("killed", 0)),
        kills_after=int(after.counts.get("killed", 0)),
        mutants=after.all_mutants,
        passed=int(after.counts.get("killed", 0)) > int(before.counts.get("killed", 0)),
    )
