# Design: crucible — an adversarial test-hardening loop for AI-built code

Date: 2026-07-09
Status: approved (design cockpit approved by Jeff 2026-07-09)
Build model: Fable 5. Repo: github.com/Jott2121/ai-agentic-code-testing (private until results).

## 1. What this is

A deterministic Python library + CLI (`crucible`, name approved) that hardens a repo's test
suite through an adversarial loop:

1. A **Tester** agent writes tests for a target module.
2. **Mutation testing** (mutmut) finds the survivors — the injected defects no test caught.
3. A **Critic** agent is handed the *named survivors* and writes tests to kill them.
4. Repeat until dry (no new kills in K rounds) or a round cap.

Every verdict is mechanical: a mutant is killed by pytest or it survives. No model ever judges
its own (or another model's) output — that is the design principle that answers the
"self-testing is disregarded" objection, and it is measured, not assumed (see §8, H2).

On top of the engine sits a **pre-registered experiment** (arXiv-standard rigor), and a
**Claude Code skill wrapper** making the loop a daily command.

## 1a. How this differs from oracle-gate

Oracle Gate is the **inspector**: it measures and refuses — run the mutation scan, name the
survivors, demand each be killed or explained by a named human, bind evidence to a commit. It
never writes a test. Crucible is the machine on the other side of the gate: it **automates the
fixing** that oracle-gate demands (the exact workflow done by hand on graph-guard Phase 1).
Mutation testing is not the product here; it is the feedback signal inside the loop, the way a
thermostat contains a thermometer. Stack: the standard says what evidence trust requires →
oracle-gate checks the evidence exists and refuses when it doesn't → crucible generates the
missing evidence automatically, under guardrails, with receipts.

## 1b. Prior art and the honest novelty claim (verified 2026-07-09)

Survivor-feedback and adversarial test loops are **published**; the claims below are scoped
accordingly. Verified primary sources:

- **MuTAP** (Dakhel et al., 2023) — first to feed surviving mutants into LLM prompts to improve
  generated tests. Single-agent, benchmark-scale.
- **AdverTest** (Chang et al., arXiv:2602.08146, 2026) — dual-agent adversarial loop (test agent
  vs *mutant-generation* agent), +8.56% fault detection over best LLM baselines on real Java
  projects. Closest neighbor.
- **Meta ACH** (Harman et al., FSE 2025) — industrial mutation-guided LLM test generation:
  10,795 classes, LLM equivalent-mutant detector (0.79P/0.47R, 0.95/0.96 with preprocessing),
  73% engineer acceptance. Closed/internal.

**What remains open, and is this project's contribution:**
1. **H2** — whether a cross-lineage Critic beats a same-lineage Critic when the oracle is
   mechanical. Not measured by any of the above (to be confirmed in the formal related-work
   pass before PROTOCOL.md freezes; if found published, H2 re-scopes or the experiment stops).
2. **Cost economics** — survivors killed per dollar, metered per stage. Not reported anywhere.
3. **Open governance-first implementation** — engine-agnostic, anti-gaming guardrails,
   SHA-bound receipts, pre-registered. ACH is closed; AdverTest is a research artifact.
4. **H1 is a replication in a new setting** (agentic, repo-level, Python, costs disclosed) —
   framed as replication, never as priority.

A formal related-work sweep is a **blocking task before PROTOCOL.md is committed**.

## 2. Decisions locked during brainstorming

| Decision | Choice | Why |
|---|---|---|
| Starting point | Fresh build on this Mac | The other session's "skeleton" never reached GitHub; nothing to salvage |
| Relationship to oracle-gate | Hard dependency (pip-installable) | One layered stack: standard → oracle-gate (gates/evidence) → crucible (agentic engine). Zero duplicated receipt/triage code |
| Rigor bar | arXiv preprint standard | Pre-registered protocol, 5 subjects, crossed design, paired stats, costs reported, null published |
| In-loop models | Staged crossed design | H1 within-lineage (Sonnet 5 / Fable 5) kills the lineage confound; H2 adds a GPT-5.6 Critic arm to measure what cross-lineage adds when the oracle is mechanical |
| Subjects | 3 of Jeff's + 2 third-party OSS | attrition-risk-ml, graph-guard, rag-guard + 2 small permissive-license Python libs (selection criteria fixed in PROTOCOL.md before selection) |
| Mutation engine | mutmut behind a seam | All existing measured baselines are mutmut; engine interface allows Cosmic Ray later without resetting claims |
| Orchestrator | Library + CLI, plus skill wrapper in scope | Loop logic is testable/mutation-testable Python; models are workers, never control flow. Wrapper ships in this build (Jeff's call) |
| Budget | Metered, no hard tripwire | Max plan through Jul 12 → front-load Claude-heavy runs; GPT + Anthropic API after. Every run metered via agent-cost-attribution |
| Publicity | Private until results, then public | Pre-registration commit timestamps still prove protocol-before-results |
| Loop stop | Round cap N + triage | Approved with the design: equivalent mutants must not stall "until dry"; leftovers go to oracle-gate survivor triage |

## 3. Architecture

```
ai-agentic-code-testing/
├── src/crucible/
│   ├── loop.py          # the adversarial loop: PURE control flow, injected env
│   ├── engine.py        # MutationEngine seam + MutmutEngine adapter
│   ├── roles.py         # Tester/Critic role construction; prompts loaded + sha256-hashed
│   ├── prompts/         # versioned prompt files (hash goes into every receipt)
│   ├── guardrails.py    # add-only, validity gate, flake check, anti-weakening
│   ├── runner.py        # pytest execution wrapper (subprocess, timeouts)
│   ├── receipts.py      # crucible-native JSON receipts, SHA-bound (oracle-gate evidence-package emission deferred)
│   ├── meter.py         # thin glue over agent-cost-attribution pricing/metering
│   └── cli.py           # crucible harden | oneshot | experiment | report
├── tests/               # unit (fake env) + integration (marked, real APIs)
├── experiments/
│   ├── PROTOCOL.md      # pre-registered; committed before any run
│   ├── subjects/        # pinned-SHA clone manifests, never vendored code
│   └── runs/            # receipts + kill matrices per run
├── skill/harden-tests/  # Claude Code skill wrapper calling the CLI
├── docs/superpowers/specs/
└── .github/workflows/   # unit tests + lint + oracle-gate ratchet (no paid runs in CI)
```

**Imported, not rebuilt** (extend-don't-fork):
- `oracle_gate.providers` — model calls with declared lineage (Claude + OpenAI).
- `oracle_gate.survivors` — survivor triage, digest-bound explanations.
- `oracle_gate.provenance` / evidence packages — receipts bound to commit SHA + artifact hashes.
- `agent-cost-attribution` — per-stage token/cost metering.

**Prerequisite:** oracle-gate is currently editable-install only. First implementation task is a
small packaging fix on the public oracle-gate repo so crucible can `pip install` it from GitHub.

### The loop (pure core, injected IO)

`loop.py` follows the oracle-gate pattern Jeff already shipped: the decision logic is a pure
function of an injected `env` exposing `run_mutation()`, `run_tests()`, `call_model(role, ...)`,
`clock/budget`. Unit tests drive it with fakes; one marked integration test uses real APIs.
This makes the loop itself mutation-testable (§7 dogfooding).

Loop state per round: `{round, survivors: [mutant ids], new_tests: [paths], kills: [mutant ids],
cost: $, verdict: continue|dry|cap|abort}` — serialized into the receipt.

## 4. Guardrails (the anti-gaming layer)

These encode the standard's known agent failure modes as hard checks, not prompts:

1. **Add-only.** Generated output may only add new test files under a `crucible_` prefix.
   Any diff touching source or existing tests → round rejected. (Kent Beck / TDD-Guard failure
   mode: agents weaken tests to pass.)
2. **Validity gate (positive+negative control).** Every generated test must PASS on pristine
   code (else it's invalid, not a kill) and the file must contain ≥1 real assertion. Tests
   failing on pristine code are logged as `invalid`, excluded from kill credit.
3. **Flake check.** New tests run twice; nondeterministic results → rejected, logged `flaky`.
4. **No oracle leakage.** The Critic is given the survivor's *diff* (what changed), never told
   "write a test asserting the current behavior is right" — prompts are versioned and hashed so
   the paper can show exactly what each role saw.
5. **Sandboxed execution.** Generated tests run via subprocess pytest with a timeout in the
   subject's venv; network access documented as a limitation (full syscall sandboxing out of
   scope, noted in PROTOCOL.md).

## 5. Error handling

- Model call fails → 3 retries w/ backoff → round aborts with receipt (`abort`, reason, cost so far).
  A failed round never counts as "dry."
- mutmut/pytest nonzero on pristine baseline → hard stop before any model is called
  (prove-upstream: subject must be green first).
- Budget/meter unavailable → runs still work, receipt marks `cost: unmetered` loudly.
- Partial round crash → receipts are append-per-round, so a crash loses at most one round.

## 6. CLI surface

- `crucible harden PATH --module M [--critic same|cross] [--rounds N]` — run the loop, emit receipt.
- `crucible oneshot PATH --module M` — the baseline arm (Tester once, no loop).
- `crucible experiment PROTOCOL.md [--arm A] [--subject S]` — run pre-registered arms; refuses to
  run if PROTOCOL.md is uncommitted or dirty.
- `crucible report RUNS_DIR` — kill matrices, paired outcomes, McNemar, cost per survivor killed.

## 7. Testing crucible itself

- TDD throughout; unit tests on the pure loop with fake env.
- Golden tests for receipts (byte-stable modulo bound fields).
- Mutation testing on `loop.py`, `guardrails.py`, `engine.py` with oracle-gate `check` ratchet
  in CI (gate the diff, warn-then-enforce — per lessons 0026/0027).
- One integration test per provider behind `-m integration` (never in CI).
- Adversarial QC pass (independent review) before declaring done — standing self-QC discipline.

## 8. The experiment (summary — PROTOCOL.md is the binding document)

- **H1 (replication, new setting):** the adversarial loop kills more survivors than one-shot
  test generation, same model, same budget disclosure. Within-lineage (Claude), paired per
  subject-module. Replicates the MuTAP/AdverTest direction in an agentic repo-level Python
  setting with disclosed costs; framed as replication (§1b).
- **H2 (the novel claim):** a cross-lineage Critic (GPT-5.6) outperforms a same-lineage Critic
  (Claude), both in-loop. Either outcome is publishable: cross-lineage value measured, or
  mechanical oracles shown to reduce the need for it. Novelty contingent on the related-work
  sweep (§1b) confirming it unmeasured.
- Arms per subject-module: (a) one-shot, (b) loop same-lineage, (c) loop cross-lineage.
- Metrics: survivors killed (full-denominator mutation score deltas reported both ways per
  lesson 0018), rounds-to-dry, cost per survivor killed, invalid/flaky rates per arm.
- Stats: McNemar on paired per-mutant kill outcomes; costs reported with meter receipts.
- Subjects pinned by SHA; third-party subjects have their existing tests stripped for the run
  (in a clone, never upstream). Training-data contamination disclosed as a limitation; the
  mutant-kill metric blunts (does not eliminate) it.
- A null result is published with the same prominence — same posture as blind-oracle-pilot.
- Sequencing: pilot on graph-guard first (go/no-go gate), then full Claude arms before Jul 12,
  GPT arm when the OpenAI key is loaded.

## 9. Skill wrapper

`skill/harden-tests/` — a Claude Code skill: "harden the tests in this repo/module" → invokes
`crucible harden`, interprets the receipt in plain English, proposes triage for leftovers.
Ships in this build (approved), after the CLI is stable.

## 10. Out of scope (YAGNI, recorded)

- Cosmic Ray adapter (seam exists; build when a measured need appears).
- LLM-generated mutants (AdverTest/ACH-style adversary-as-mutator) — Phase-later research, not
  needed for H1/H2; if added, AdverTest and ACH are the prior art to cite.
- Property/metamorphic generation layer (incl. PROBE-style adversarial property-based testing),
  dashboards, risk-tier governance features — later phases of Jeff's roadmap, deliberately cut.
- Safety/robustness/fuzzing frameworks from the survey list (Vera, TREAT, PtTrust, Flare,
  BMC-Agent, commercial QA platforms) — unverified names as of 2026-07-09; related-work
  candidates at most, never build scope for v1.
- PII/bias compliance engine — different product (rag-guard territory); HR angle lives in the
  attrition-risk-ml worked example.
- Full syscall sandboxing of generated tests.

## 11. Risks (from the approved cockpit)

- **HI — equivalent mutants stall "until dry."** Mitigation: round cap + oracle-gate triage +
  both denominators reported. (Approved.)
- **MED — subjects in training data flatter one-shot.** Disclosed; mutant-kill metric blunts it.
- **MED — mutmut wall-clock across 5 subjects × 3 arms × rounds.** Scope to 1-2 modules per
  subject, cache baseline mutants, front-load Claude arms.
- **LO — GPT arm slips past Jul 12.** H1 completes on Max; H2 runs on API later.
