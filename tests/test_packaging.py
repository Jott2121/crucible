"""Prove the dependency story before building on it: crucible imports, and the two
upstream packages it extends (oracle-gate, agent-cost-attribution) import from the venv.

Also guards the metadata that only PyPI validates, on the one push that cannot be retried."""
import tomllib
from pathlib import Path

import pytest
from trove_classifiers import classifiers as VALID_CLASSIFIERS


def _pyproject():
    """Walk up for pyproject.toml rather than assuming a fixed depth.

    Under mutmut the tests execute from the `mutants/` sandbox copy, which does
    not contain pyproject.toml. A hardcoded `parents[1]` would raise there and be
    scored as a failing test inside the sandbox -- the plausible-zero class this
    repo already has receipts for. Walking up finds the real file from either
    location, and skips honestly if it genuinely is not reachable.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            data = tomllib.loads(candidate.read_text(encoding="utf-8"))
            if data.get("project", {}).get("name") == "crucible-harden":
                return data
    pytest.skip("crucible's pyproject.toml is not reachable from here")


def test_classifiers_are_real_trove_classifiers():
    """PyPI rejects an unknown classifier with a 400 at upload time, and `twine
    check` does NOT catch it -- twine only checks that the description renders.
    So the invalid classifier survives every local gate and fails on the single
    irreversible step. This is the check that actually catches it.

    Receipt: `Topic :: Software Development :: Testing :: Mutation` looked
    obviously real, does not exist, and failed the first crucible-harden upload.
    """
    declared = _pyproject()["project"]["classifiers"]
    assert declared, "classifiers disappeared from pyproject.toml"
    unknown = [c for c in declared if c not in VALID_CLASSIFIERS]
    assert not unknown, f"not real trove classifiers: {unknown}"


def test_dependencies_carry_no_direct_urls():
    """PyPI refuses any distribution whose Requires-Dist contains a direct URL,
    so a `pkg @ git+https://...` pin silently makes the project unpublishable.
    That is what blocked this package until oracle-gate and agent-cost-attribution
    were themselves released.
    """
    deps = _pyproject()["project"]["dependencies"]
    direct = [d for d in deps if "@" in d or d.startswith(("git+", "http"))]
    assert not direct, f"direct-URL dependencies cannot be published to PyPI: {direct}"


def test_crucible_imports():
    import crucible
    assert crucible.__version__ == "0.1.0"


def test_oracle_gate_importable():
    from oracle_gate import providers, survivors, runner, provenance  # noqa: F401


def test_meter_importable():
    from agent_cost_attribution import pricing  # noqa: F401
    assert "fable" in pricing.PRICES
