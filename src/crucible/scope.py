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
    waived: bool = False


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
# positional params) plus a few common container shapes (empty list/dict/str,
# a list-of-dict, and their 2-arity pairings) -- TypeError from an arity
# mismatch is skipped; any OTHER exception (e.g. a boundary condition mutated
# into a ZeroDivisionError) is left to propagate as a genuine, mechanically
# real kill WHEN a real mutant is under test, and tolerated otherwise (see
# _UNDER_MUTANT in _CANARY below).
_CANARY_PROBES = [(), (0,), (1,), (0, 0), (1, 0), (0, 1), (1, 1), (-1, 1),
                   (0, 0, 0), (5, 0, 10), (-1, 0, 10), (11, 0, 10),
                   ([],), ({},), ("",), ([{}],), ([], 0), (0, [])]

_CANARY = (
    "import importlib\n"
    "import os\n"
    "mod = importlib.import_module({modname!r})\n"
    "_NAMES = {names!r}\n"
    "_PROBES = {probes!r}\n"
    # mutmut's trampoline (mutmut/mutation/trampoline.py) sets MUTANT_UNDER_TEST
    # to "{module}.{mutant_name}" while a specific mutant is active, to "stats"
    # during its own pre-mutation baseline/coverage pass, and leaves it unset
    # for any direct pytest invocation (our own pristine check). Only the first
    # case is "a real mutant is running right now" -- "stats" and unset both
    # execute the ORIGINAL function, so a probe exception there is a genuine
    # domain-validation exception on unmutated code, not a mutation-induced
    # crash, and must never be allowed to fail the run.
    "_UNDER_MUTANT = os.environ.get('MUTANT_UNDER_TEST', '') not in ('', 'stats', 'fail')\n"
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
    "            except Exception:\n"
    "                if _UNDER_MUTANT:\n"
    "                    raise\n"
    "                continue\n"
    "            else:\n"
    "                break\n"
)


def canary_probe(subject_dir: Path, module: str, run=subprocess.run) -> CanaryVerdict:
    """Must-kill collection proof before any model spend (v6 lesson) -- TWO-BRANCH
    policy (amended 2026-07-11, owner-approved): a fresh canary test is only
    written and measured when there is no cheaper mechanical proof already
    available.

    Policy and justification: first measure the EXISTING suite's baseline
    kill count under this scope, before writing anything. If that baseline
    already kills at least one mutant (before.killed > 0), that fact alone IS
    mechanical proof that mutmut collects and executes tests here -- the
    exact v6 failure class this gate exists to catch (a scope so broken that
    no test file, however written, is ever collected) cannot be true if an
    existing test is already registering kills under it. The marginal "can a
    BRAND NEW file also get collected" canary is redundant in that case, so
    it is skipped entirely -- no canary is written, no pristine check runs,
    and no second (expensive) mutmut measure happens; the verdict is
    WAIVED-passed on the strength of the existing suite alone.

    Only when the baseline is a genuine zero (an empty or too-weak-to-kill
    suite -- exactly the original v6 disaster case, where a scope defect can
    silently swallow every test including freshly generated ones, and no
    existing test offers any counter-proof) does the strict must-kill canary
    run: write a canary test, prove it passes on pristine code (so a broken
    PROBE, not the subject, is what's ever blamed), measure again, and
    require the kill count to strictly increase.

    Residual/dependency: a WAIVED verdict proves collection of the EXISTING
    test files only, for the module as scoped right now. It does NOT
    independently re-prove that a brand-new crucible_*_test.py written later
    in the loop will also be collected -- that ongoing guarantee still rests
    entirely on scope.detect()/apply() always writing
    pytest_add_cli_args_test_selection in EXCLUDE form (never an
    include-list; the v6 lesson) so newly generated test files are never
    accidentally filtered out. The waiver and the exclude-only scope-writer
    are companion guarantees, not substitutes for each other.

    The "before" measure happens first and unconditionally, so a waived scope
    never pays for writing or pristine-checking a canary at all; only the
    strict branch writes one, and it is always removed in a finally, pass or
    fail."""
    subject_dir = Path(subject_dir)
    modname = module[:-3].replace("/", ".")
    if modname.startswith("src."):
        modname = modname[len("src."):]          # v7: bare name, never src.-qualified
    engine = MutmutEngine(subject_dir, run=run)
    before = engine.measure()
    before_killed = int(before.counts.get("killed", 0))
    if before_killed > 0:
        return CanaryVerdict(
            kills_before=before_killed,
            kills_after=before_killed,
            mutants=before.all_mutants,
            passed=True,
            waived=True,
        )
    names = _public_top_level_names(subject_dir / module)
    tests_dir = subject_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    canary = tests_dir / "crucible_canary_test.py"
    try:
        canary.write_text(_CANARY.format(modname=modname, names=names, probes=_CANARY_PROBES))
        pristine = run([sys.executable, "-m", "pytest", "-q", str(canary), "--ignore=mutants"],
                       cwd=str(subject_dir), capture_output=True, text=True, timeout=300)
        if pristine.returncode != 0:
            raise RuntimeError(
                "canary failed on pristine code -- the probe is wrong, not the subject: "
                f"{(pristine.stdout or '')[-400:]}")
        after = engine.measure()
    finally:
        canary.unlink(missing_ok=True)
    after_killed = int(after.counts.get("killed", 0))
    return CanaryVerdict(
        kills_before=before_killed,
        kills_after=after_killed,
        mutants=after.all_mutants,
        passed=after_killed > before_killed,
        waived=False,
    )
