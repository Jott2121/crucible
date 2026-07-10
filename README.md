# crucible

**Status: private until pre-registered results are in.**

Adversarial test-hardening for AI-built code. A Tester agent writes tests; mutation testing
(mutmut) finds the survivors — injected defects no test caught; a Critic agent is handed the
named survivors and writes tests to kill exactly those; the loop runs until dry. Every verdict
is mechanical (pytest kills the mutant or it survives) — no model ever judges model output.

Built on [oracle-gate](https://github.com/Jott2121/oracle-gate): the gate demands evidence,
crucible generates it. Survivor triage, provenance, and cross-model providers are imported
from oracle-gate, not rebuilt. Spend is metered exactly per round (input/output split) via
agent-cost-attribution rates.

## Quickstart

    pip install -e ".[dev]"
    crucible harden /path/to/subject-clone --module pkg/module.py
    crucible report runs/<run-dir>

Design spec: docs/superpowers/specs/2026-07-09-agentic-testing-framework-design.md
Prior art and claims ledger: spec section 1b (MuTAP, AdverTest, Meta ACH).
