"""Guard the distribution metadata that only PyPI validates, plus the one promise
PyPI cannot validate at all.

PyPI rejects an unknown classifier, and any direct-URL dependency, with a 400 at
upload time. `twine check` catches neither -- it only validates that the long
description renders. So both defects pass every local gate and surface on the one
step that cannot be retried, since a version number is never reusable.

The `requires-python` floor is worse: nothing anywhere validates it. It is a claim
about code that only running the code can check.
"""
import re
from pathlib import Path

try:                                  # tomllib is stdlib only from 3.11
    import tomllib
except ModuleNotFoundError:           # this package still supports 3.9/3.10
    import tomli as tomllib

from trove_classifiers import classifiers as VALID_CLASSIFIERS

DISTRIBUTION = "crucible-harden"


def _pyproject_path():
    """Locate this project's pyproject.toml by walking up from the test file.

    Deliberately raises rather than skips when it cannot be found: a metadata guard
    that silently no-ops is worse than no guard, because it reports green.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            data = tomllib.loads(candidate.read_text(encoding="utf-8"))
            if data.get("project", {}).get("name") == DISTRIBUTION:
                return candidate
    raise AssertionError(
        f"no pyproject.toml for {DISTRIBUTION} above {Path(__file__).resolve()}"
    )


def _pyproject():
    return tomllib.loads(_pyproject_path().read_text(encoding="utf-8"))


def _floor():
    floor = _pyproject()["project"]["requires-python"].lstrip(">=").strip()
    return floor, tuple(int(p) for p in floor.split("."))


def test_classifiers_are_real_trove_classifiers():
    declared = _pyproject()["project"].get("classifiers", [])
    assert declared, "classifiers disappeared from pyproject.toml"
    unknown = [c for c in declared if c not in VALID_CLASSIFIERS]
    assert not unknown, f"not real trove classifiers: {unknown}"


def test_no_direct_url_dependencies_anywhere():
    """Extras count too -- optional dependencies land in Requires-Dist just the same."""
    project = _pyproject()["project"]
    deps = list(project.get("dependencies", []))
    for extra_deps in project.get("optional-dependencies", {}).values():
        deps += list(extra_deps)
    direct = [d for d in deps if "@" in d or d.startswith(("git+", "http"))]
    assert not direct, f"direct-URL dependencies cannot be published to PyPI: {direct}"


def test_ci_actually_tests_the_lowest_supported_python():
    """The floor is a promise that nothing verifies unless CI runs on it.

    This is the check for the real bug class, and the reason it exists: oracle-gate
    0.1.0 shipped `requires-python = ">=3.10"` over an unconditional `import tomllib`
    (stdlib only in 3.11+), so `pip install` succeeded on 3.10 and the CLI died at
    import. Its CI matrix only ever ran 3.11-3.13, so nothing contradicted the claim.
    No metadata-only check can see this: the classifiers and the floor agreed with
    each other, and were wrong together.
    """
    root = _pyproject_path().parent
    ci = root / ".github" / "workflows" / "ci.yml"
    if not ci.is_file():                       # package in a subdirectory of the repo
        ci = root.parent / ".github" / "workflows" / "ci.yml"
    assert ci.is_file(), f"no CI workflow found near {root}; the floor is unverified"
    matrix = re.search(r"python-version:\s*\[([^\]]+)\]", ci.read_text(encoding="utf-8"))
    assert matrix, "could not find a python-version matrix in ci.yml"
    tested = sorted(
        tuple(int(p) for p in v.split("."))
        for v in re.findall(r"[\"']([\d.]+)[\"']", matrix.group(1))
    )
    assert tested, "python-version matrix parsed as empty"
    floor, floor_key = _floor()
    assert tested[0] == floor_key, (
        f"requires-python claims >={floor} but the lowest version CI runs is "
        f"{'.'.join(str(p) for p in tested[0])}; the floor is an untested promise"
    )


def test_declared_python_floor_matches_the_classifiers():
    """A `Programming Language :: Python :: X.Y` claim below requires-python is a lie
    pip will honour: the install succeeds and the code fails at import.
    """
    project = _pyproject()["project"]
    floor, floor_key = _floor()
    claimed = [
        c.rsplit(" :: ", 1)[1]
        for c in project.get("classifiers", [])
        if c.startswith("Programming Language :: Python :: ") and c[-1].isdigit()
    ]
    versions = [tuple(int(p) for p in c.split(".")) for c in claimed if "." in c]
    below = [".".join(str(p) for p in v) for v in versions if v < floor_key]
    assert not below, f"classifiers claim Python {below} but requires-python is >={floor}"


def test_crucible_imports():
    import crucible
    assert crucible.__version__ == "0.1.1"


def test_oracle_gate_importable():
    from oracle_gate import providers, survivors, runner, provenance  # noqa: F401


def test_meter_importable():
    from agent_cost_attribution import pricing  # noqa: F401
    assert "fable" in pricing.PRICES
    # public API since agent-cost-attribution 0.1.1; crucible no longer reaches
    # for the private `_tier`
    assert pricing.tier("claude-sonnet-5") == "sonnet"
