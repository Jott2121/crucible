# crucible

[![ci](https://github.com/Jott2121/crucible/actions/workflows/ci.yml/badge.svg)](https://github.com/Jott2121/crucible/actions/workflows/ci.yml)

**Your AI wrote the tests. Who tested the tests?**

Coverage measures what ran, not what would be caught. Mutation testing injects real defects
and counts how many your suite kills — and AI-written suites routinely leave survivors.
crucible closes the loop: a **Tester** agent writes tests, **mutmut** finds the survivors —
injected defects no test caught — and a **Critic** agent is handed the named survivors and
writes tests to kill exactly those. Every verdict is mechanical: pytest kills the mutant or
it survives. **No model ever grades model output.**

## Quickstart — the free first win (no model, no keys, ~10 minutes)

Find out what your existing tests miss, on your own repo:

    git clone https://github.com/Jott2121/crucible && pip install -e "./crucible[dev]"
    cd /path/to/your-repo-clone       # work in a clone: crucible writes scope config
    crucible scope . --module yourpkg/yourmodule.py
    mutmut run && mutmut results      # survivors = injected bugs your tests never caught

`crucible scope` detects your layout, writes the mutation scope, and **proves** a fresh test
file is collectable before anything else runs (a canary probe; it refuses — exit 4 — rather
than guess). No AI is involved yet: the survivor count is plain mutation testing on your suite.

## Then harden — the adversarial loop

    crucible harden . --module yourpkg/yourmodule.py \
        --tester claude-cli --critic claude-cli --runs-dir ~/.crucible-runs/yourrepo

With `claude-cli`, model calls run through Claude Code headless on your Claude subscription —
**$0 metered spend**, and every run's `meta.json` records `billing: max-plan` so plan-covered
shadow dollars are never mistaken for an invoice. No subscription? `--tester anthropic` uses the
metered API via `ANTHROPIC_API_KEY`.

Lean invocation is the default: the subprocess runs with `--tools ""`, collapsing Claude
Code's agent loop to a single completion. On the reference run (`rag_guard/guard.py`), that
took the harden from **439,230 to 3,641 input tokens (120.6×), with identical results — the
same 25/25 surviving mutants killed** (receipts `20260712T050833Z` vs `20260712T171312Z`).
Measured on that run's receipts, not a universal constant. `CRUCIBLE_LEAN=0` restores the
ambient invocation.

## Receipts are the product

Every run writes a receipt directory:

    meta.json         # models, billing (api vs max-plan), lean_isolation rung, scope commit
    receipt.jsonl     # one line per round: tokens in/out, cost, kills, survivors, prompt hash
    result.json       # verdict + totals

Generated tests are written into the working tree of wherever you run it — so run it on a
throwaway branch; the bundled `harden-tests` skill (`.claude/skills/harden-tests/`) enforces
the full ritual: **local branch only, never main, PR strictly opt-in**. If the canary can't
prove your scope, crucible refuses instead of spending tokens.

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

## Why trust this

The claims above are checkable: the experiment was pre-registered before results existed
(`experiments/PROTOCOL.md`), the null is published at the same prominence as the positive
result, the prior art is cited rather than rediscovered (`docs/RELATED-WORK.md`), and the
tool is dogfooded — crucible's own modules run under the same mutation gate, current score
and survivor dispositions in `docs/MUTATION.md`.

## Honest limitations

- Python + pytest repos only; layout heuristics target well-formed projects — a repo the
  canary can't validate is a refusal, not a guess.
- mutmut is pinned exactly (3.6.0): the src-layout shim relies on a mutmut-internal contract.
- The `claude-cli` provider has no mechanical truncation check (the CLI exposes no output
  cap); disclosed in the provider docstring.
- The 120.6× lean result is one module, one apples-to-apples pair of runs. Your ratio will
  differ; your receipts will tell you.

## How it works

    Tester (writes tests) ──> mutmut (injects defects, counts kills)
          ^                        │ named survivors
          └──── Critic (kills exactly those) <──┘   ... until dry or round cap

Built on [oracle-gate](https://github.com/Jott2121/oracle-gate) (survivor triage, provenance,
providers). MIT license.
