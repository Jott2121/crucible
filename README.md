# crucible

**Status: private — pre-registered results are in.**

Adversarial test-hardening for AI-built code. A Tester agent writes tests; mutation testing
(mutmut) finds the survivors — injected defects no test caught; a Critic agent is handed the
named survivors and writes tests to kill exactly those; the loop runs until dry. Every verdict
is mechanical (pytest kills the mutant or it survives) — no model ever judges model output.

Built on [oracle-gate](https://github.com/Jott2121/oracle-gate): the gate demands evidence,
crucible generates it. Survivor triage, provenance, and cross-model providers are imported
from oracle-gate, not rebuilt. Spend is metered exactly per round (input/output split) via
agent-cost-attribution rates.

## Results

The pre-registered experiment (`experiments/PROTOCOL.md`) ran five subjects (graph-guard,
rag-guard, packaging, idna, attrition-risk-ml) across three arms (one-shot, same-lineage
adversarial loop, cross-lineage adversarial loop). **H1** (the adversarial loop kills more
mutants than one-shot generation, replicating the MuTAP→AdverTest direction in a new
agentic/repo-level/Python setting) is **supported**: pooled exact McNemar p = 3.4×10⁻¹⁸, favoring
the loop, both with and without the degenerate zero-baseline subject included. **H2** (a
cross-lineage critic, GPT-5.6-terra, kills more of a same-lineage critic's, claude-sonnet-5's,
missed survivors than another same-lineage critic does) is **supported with a load-bearing
caveat**: pooled p = 9.5×10⁻⁶⁶ favoring cross-lineage, but the effect is concentrated in two of
four scorable subjects (one subject's cell was rejected and excluded per protocol, two more hit a
ceiling effect with zero discordant pairs available), and part of the strongest subject's gap
traces to same-lineage critic rounds being rejected on validity/format grounds rather than to
categorically weaker test content. Full tables, three pre-declared McNemar views, cost-per-kill,
wrong-oracle-drop counts, an instrument-repair narrative (three silent-corruption mechanisms
caught by fail-closed gates before these numbers were computed), and total spend are in
[`experiments/RESULTS.md`](experiments/RESULTS.md).

## Quickstart

    pip install -e ".[dev]"
    crucible harden /path/to/subject-clone --module pkg/module.py
    crucible report runs/<run-dir>

Design spec: docs/superpowers/specs/2026-07-09-agentic-testing-framework-design.md
Prior art and claims ledger: spec section 1b (MuTAP, AdverTest, Meta ACH).
