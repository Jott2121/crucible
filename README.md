# crucible

**Pre-registered results are in — including a published null.**

Adversarial test-hardening for AI-built code. A Tester agent writes tests; mutation testing
(mutmut) finds the survivors — injected defects no test caught; a Critic agent is handed the
named survivors and writes tests to kill exactly those; the loop runs until dry. Every verdict
is mechanical (pytest kills the mutant or it survives) — no model ever judges model output.

Built on [oracle-gate](https://github.com/Jott2121/oracle-gate): the gate demands evidence,
crucible generates it. Survivor triage, provenance, and cross-model providers are imported
from oracle-gate, not rebuilt. Spend is metered exactly per round (input/output split) via
agent-cost-attribution rates.

## Results

The pre-registered experiment (`experiments/PROTOCOL.md`) ran five subjects across three arms
(one-shot, same-lineage adversarial loop, cross-lineage adversarial loop). **H1** — the
adversarial loop kills more mutants than one-shot generation — is **supported**: pooled exact
McNemar p = 4.9×10⁻³², b = 105, c = 0. This **replicates** the direction established by MuTAP,
AdverTest, and Meta's ACH (see `docs/RELATED-WORK.md`) in a new agentic, repo-level, Python
setting — we claim the replication, not the idea. **H2** — a cross-lineage critic beats a
same-lineage critic on missed survivors — is **not supported** (p = 0.0625). An earlier run
showed an enormous H2 effect; the autopsy traced it to silent output truncation rejecting one
arm's rounds — an instrument artifact, not a model difference. That autopsy, and the fail-closed
instrumentation built from it, is the finding. Full tables, all three pre-declared views,
cost-per-kill, and the instrument-repair narrative: [`experiments/RESULTS.md`](experiments/RESULTS.md).

## Quickstart

    pip install -e ".[dev]"
    crucible harden /path/to/subject-clone --module pkg/module.py
    crucible report runs/<run-dir>

Design spec: docs/superpowers/specs/2026-07-09-agentic-testing-framework-design.md
Prior art and claims ledger: spec section 1b (MuTAP, AdverTest, Meta ACH).
