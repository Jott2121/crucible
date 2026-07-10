"""Prove the dependency story before building on it: crucible imports, and the two
upstream packages it extends (oracle-gate, agent-cost-attribution) import from the venv."""


def test_crucible_imports():
    import crucible
    assert crucible.__version__ == "0.1.0"


def test_oracle_gate_importable():
    from oracle_gate import providers, survivors, runner, provenance  # noqa: F401


def test_meter_importable():
    from agent_cost_attribution import pricing  # noqa: F401
    assert "fable" in pricing.PRICES
