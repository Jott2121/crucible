# RESULTS — Crucible Experiment (H1 replication, H2 novel claim)

Every number below is recomputed from the committed receipts under `experiments/runs/` by
`experiments/analyze.py` (stdlib, tested against crafted receipt dirs in
`tests/test_analyze.py`), driven by the committed manifest `experiments/counted.json`. The
machine-readable form of every figure in this document is `experiments/results.json`, written by
the same script. Reproduce with:

    source .venv/bin/activate && python experiments/analyze.py

The pre-registered protocol is `experiments/PROTOCOL.md`; every departure from it is logged in
`experiments/DEVIATIONS.md`. Verdicts below apply the support criteria PROTOCOL.md §5 fixed
*before any paid run* — quoted here, then the numbers, with no criteria chosen after seeing
results.

## Counted cells

Five subjects × three arms = 15 counted cells, one paired run per subject-module per arm, listed
with justification in `experiments/counted.json`. Every other directory under
`experiments/runs/` (12 additional dirs, 27 total minus 15) is shakeout or instrument-invalid —
preserved as evidence, excluded from every metric below. See "Instrument-repair narrative" for
why.

| Subject | oneshot | loop-same | loop-cross |
|---|---|---|---|
| graph-guard | `oneshot-20260710T191723Z` | `loop-same-20260710T191858Z` | `loop-cross-20260710T194101Z` |
| rag-guard | `oneshot-20260710T192857Z` | `loop-same-20260710T192933Z` | `loop-cross-20260710T194336Z` |
| packaging | `oneshot-20260710T181053Z` | `loop-same-20260710T181157Z` | `loop-cross-20260710T194516Z` |
| idna | `oneshot-20260710T181906Z` | `loop-same-20260710T182018Z` | `loop-cross-20260710T194820Z` |
| attrition-risk-ml | `oneshot-20260710T193041Z` | `loop-same-20260710T193123Z` | `loop-cross-20260710T195033Z` |

## Full cell table

Kill counts are per-mutant, over each subject's own pristine-baseline survivor set (round 0's
`survivors_before`, measured before any generated test exists). `rate%` = killed / baseline
survivors, one decimal; `$/kill` = `total_cost_usd / killed` (`n/a` when killed = 0, never
divided by zero). `dropped` = wrong-oracle tests salvaged away by
`crucible.guardrails.salvage_new_tests` (protocol_version 3) across all rounds — never counted as
a kill.

| Subject | Arm | Verdict | Baseline survivors | Killed | Rate | Cost ($) | $/kill | Dropped |
|---|---|---|---:|---:|---:|---:|---:|---:|
| graph-guard | oneshot | oneshot | 22 | 12 | 54.5% | 0.1265 | 0.0105 | 0 |
| graph-guard | loop-same | dry | 22 | 11 | 50.0% | 0.6061 | 0.0551 | 1 |
| graph-guard | loop-cross | **rejected** | 22 | 0 | 0.0% | 0.2437 | n/a | 0 |
| rag-guard | oneshot | oneshot | 25 | 21 | 84.0% | 0.0553 | 0.0026 | 0 |
| rag-guard | loop-same | clean | 25 | 25 | 100.0% | 0.1073 | 0.0043 | 0 |
| rag-guard | loop-cross | clean | 25 | 25 | 100.0% | 0.1582 | 0.0063 | 1 |
| packaging | oneshot | oneshot | 69 | 36 | 52.2% | 0.1139 | 0.0032 | 0 |
| packaging | loop-same | dry | 69 | 36 | 52.2% | 0.6916 | 0.0192 | 0 |
| packaging | loop-cross | dry | 69 | 68 | 98.6% | 0.2963 | 0.0044 | 3 |
| idna | oneshot | oneshot | 187 | 123 | 65.8% | 0.1232 | 0.0010 | 0 |
| idna | loop-same | clean | 187 | 187 | 100.0% | 0.6482 | 0.0035 | 9 |
| idna | loop-cross | clean | 187 | 187 | 100.0% | 0.1883 | 0.0010 | 0 |
| attrition-risk-ml | oneshot | oneshot | 255 | 62 | 24.3% | 0.0656 | 0.0011 | 0 |
| attrition-risk-ml | loop-same | dry | 255 | 69 | 27.1% | 0.8093 | 0.0117 | 0 |
| attrition-risk-ml | loop-cross | cap | 255 | 254 | 99.6% | 0.3397 | 0.0013 | 2 |

Per PROTOCOL.md §3.1/§4, **attrition-risk-ml's numbers above are absolute (kills and rates for
one arm), never a ratio against another arm** — its 0-kill pristine baseline makes any
relative-improvement figure meaningless by construction.

## H1 — replication: does the adversarial loop kill more than one-shot?

> **Pre-written support criterion (PROTOCOL.md §5).** "H1 supported if and only if the pooled
> McNemar test (H1 comparison: `loop-same` vs `oneshot`, discordant pairs across all five
> subjects) yields p < 0.05, and the direction favors `loop-same` (more mutants killed by
> `loop-same` than by `oneshot` among the discordant pairs, i.e. b > c where b = loop-same-only
> kills). Any other outcome ... is not supported." The **pooled-with-attrition** view is fixed as
> the confirmatory statistic; pooled-without-attrition and per-subject are pre-declared companion
> readouts, always reported, never substituted for the decision.

### Per-subject 2×2 (paired over each subject's baseline union)

| Subject | both | b (loop-same only) | c (oneshot only) | neither | p (exact McNemar) | Favors loop-same |
|---|---:|---:|---:|---:|---:|:---:|
| graph-guard | 11 | 0 | 1 | 10 | 1.000000 | No |
| rag-guard | 21 | 4 | 0 | 0 | 0.125000 | Yes |
| packaging | 32 | 4 | 4 | 29 | 1.000000 | No (tie) |
| idna | 123 | 64 | 0 | 0 | 1.084e-19 | Yes |
| attrition-risk-ml | 62 | 7 | 0 | 186 | 0.015625 | Yes |

### Pooled views (both pre-declared)

| View | b | c | p (exact McNemar, two-sided) |
|---|---:|---:|---:|
| **Pooled-with-attrition (confirmatory)** | 79 | 5 | **3.402e-18** |
| Pooled-without-attrition (companion) | 72 | 5 | 2.804e-16 |

### Verdict: H1 SUPPORTED

Pooled-with-attrition p = 3.4×10⁻¹⁸ < 0.05, and b = 79 > c = 5 → direction favors `loop-same`.
Both criteria of the pre-written rule are met. The pooled-without-attrition companion view agrees
(p = 2.8×10⁻¹⁶, b = 72 > c = 5) — no robustness disagreement to report.

**Effect sizes, reported regardless of significance (per-subject mixed picture):** three of five
subjects individually favor `loop-same` (rag-guard +4, idna +64, attrition-risk-ml +7 absolute
discordant kills), one subject ties exactly (packaging, 4-for-4), and one subject's *point
estimate* favors `oneshot` by a single discordant pair (graph-guard, 0 vs 1 — not itself
significant at n=1, p=1.0). The pooled confirmatory verdict is driven overwhelmingly by idna (64
of the pooled 79 loop-same-only kills) and is not a case of five subjects independently agreeing;
this is disclosed, not hidden, and is exactly why PROTOCOL.md §5 fixes the pooled statistic as the
decision rule and reports per-subject figures only as a companion, not as five independent tests.

## H2 — novel claim: does a cross-lineage critic kill more survivors than a same-lineage critic?

> **Pre-written support criterion (PROTOCOL.md §5).** "H2 supported if and only if the pooled
> McNemar test (H2 comparison: `loop-cross` vs `loop-same`, discordant pairs across all five
> subjects) yields p < 0.05, and the direction favors `loop-cross` ... Any other outcome is not
> supported; a null here is itself the second publishable finding ... and is reported with the
> same prominence as a supported result."

### graph-guard's missing H2 cell (PROTOCOL.md §6)

graph-guard's counted `loop-cross` cell (`loop-cross-20260710T194101Z`) has verdict `rejected`:
round 0 (the tester round) failed the pristine-validity gate (`"invalid: fails on pristine
code\n\nno tests ran in 0.07s"`) before any test was ever accepted, so it carries zero valid kill
data. PROTOCOL.md §6 is explicit: "Aborted runs are a missing cell... It is never silently
backfilled or estimated." Per that rule, graph-guard is **excluded** from H2's per-subject table
and from **both** pooled H2 views below — not scored as a `loop-cross` zero, which would
understate `loop-cross` unfairly. graph-guard's H1 cells (oneshot, loop-same) are unaffected and
fully counted above; its $0.24 loop-cross spend is included in total spend accounting as a real,
non-refundable cost of a rejected cell.

### Per-subject 2×2 (paired over each subject's baseline union)

| Subject | both | b (loop-cross only) | c (loop-same only) | neither | p (exact McNemar) | Favors loop-cross |
|---|---:|---:|---:|---:|---:|:---:|
| graph-guard | — | — | — | — | — | **EXCLUDED — missing cell (rejected at tester round)** |
| rag-guard | 25 | 0 | 0 | 0 | 1.000000 | No (no discordant pairs — ceiling) |
| packaging | 36 | 32 | 0 | 1 | 4.657e-10 | Yes |
| idna | 187 | 0 | 0 | 0 | 1.000000 | No (no discordant pairs — ceiling) |
| attrition-risk-ml | 69 | 185 | 0 | 1 | 4.078e-56 | Yes |

### Pooled views (both pre-declared, both over the four subjects with a valid loop-cross cell)

| View | b | c | p (exact McNemar, two-sided) | Subjects pooled |
|---|---:|---:|---:|---|
| **Pooled-with-attrition (confirmatory)** | 217 | 0 | **9.496e-66** | attrition-risk-ml, idna, packaging, rag-guard |
| Pooled-without-attrition (companion) | 32 | 0 | 4.657e-10 | idna, packaging, rag-guard |

### Verdict: H2 SUPPORTED, with a load-bearing caveat

Pooled-with-attrition p = 9.5×10⁻⁶⁶ < 0.05, and b = 217 > c = 0 → direction favors `loop-cross`.
Both criteria are met. The pooled-without-attrition companion view (excluding attrition-risk-ml,
per §3.1) also supports the same direction and remains significant (p = 4.7×10⁻¹⁰, b = 32 > c =
0) — no robustness disagreement to report, but the magnitude drops sharply once attrition-risk-ml
is removed (b: 217 → 32), which is exactly why that view exists.

**Read this result with its full texture, not the p-value alone (blind-oracle-pilot posture,
PROTOCOL.md §5's "reported with the same prominence" rule applies to nuance as much as to
nulls):**

- **Two of four scored subjects contribute zero information.** rag-guard and idna both hit a
  **ceiling effect**: `loop-same` already kills 100% of its own pristine baseline (25/25 and
  187/187 respectively — see the full cell table), so there are structurally zero discordant
  pairs left for `loop-cross` to win *or* lose on those subjects. H2's entire signal comes from
  **two subjects**: packaging (b=32) and attrition-risk-ml (b=185).
- **attrition-risk-ml's 185-kill discordance is partly a same-lineage rejection story, not purely
  a cross-lineage-superiority story.** Inspecting the receipts directly
  (`experiments/runs/attrition-risk-ml/loop-same-20260710T193123Z/receipt.jsonl`): `loop-same`'s
  round 0 (tester) killed 69, then its two critic rounds were **both rejected** — round 1 on
  `"expected exactly one fenced python block, found 0"` (a response-format failure, not a test
  content judgment) and round 2 on `"invalid: fails on pristine code"` — hitting the 2-consecutive-
  dry-rounds stop with zero critic contribution. `loop-cross`
  (`loop-cross-20260710T195033Z`) by contrast ran 3 **accepted** critic rounds (+112, +82, +2
  kills) before its round 4 was rejected and the cap (`max_rounds=4`) was hit. The 185-kill gap is
  real, mechanically scored, and correctly counted per PROTOCOL.md §6 (a rejected round
  contributes zero kills regardless of cause) — but a reader should know it is driven
  substantially by the same-lineage critic's rounds failing validity/format checks here, not only
  by the cross-lineage critic finding categorically better mutants.
- **packaging's b=32 is a cleaner instance of the claim as stated**: both critics ran accepted
  rounds; `loop-cross` simply killed more of the discordant survivors (68 of 69 total vs 36 of 69
  for `loop-same`).

**Net reading:** the pooled statistic clears the pre-registered bar and both pooled views agree on
direction, so H2 is **supported** by the letter of PROTOCOL.md §5. But the effect is concentrated
in two of four scorable subjects, is partly confounded with critic-round rejection/format-
compliance differences rather than being purely a "found harder-to-kill mutants" story, and one
subject (graph-guard) never got scored at all. This is reported at the same prominence as the
p-value, per §5's own instruction that a result's nuance gets the same billing as its
significance.

## Cost-per-kill

Aggregated across all five subjects' counted cells (`total_cost_usd` summed / `killed` summed per
arm — never averaged per-subject ratio, which would let a low-kill subject's noisy ratio dominate):

| Arm | Total cost ($) | Total killed | Aggregate $/kill |
|---|---:|---:|---:|
| oneshot | 0.4844 | 254 | 0.0019 |
| loop-same | 2.8625 | 328 | 0.0087 |
| loop-cross | 1.2262 | 534 | 0.0023 |

**The GPT-5.6-terra `loop-cross` arm is ~3.8× cheaper per kill than the same-lineage `loop-same`
arm** ($0.0023 vs $0.0087), despite GPT-5.6-terra's input rate being only slightly cheaper than
claude-sonnet-5's ($2.50 vs $3.00 per MTok in, same $15 per MTok out — `crucible.meter.RATES_EXTRA`).
The gap is not primarily a rate-card effect: it is driven by `loop-cross` producing far more
*accepted* critic rounds per dollar spent (packaging and attrition-risk-ml both ran multiple
accepted `loop-cross` critic rounds that each converted into large kill batches, where the parallel
`loop-same` cells spent comparable or more dollars on critic rounds that were rejected and
contributed zero kills — see the H2 discussion above). Per `docs/RELATED-WORK.md` Claim 2, this
project's cost-per-kill figure is, to our knowledge, the first such per-outcome cost accounting in
this literature (AdverTest reports $0.270/method-run, TestForge $0.63/file — neither divides by
outcome).

## Wrong-oracle drops

`crucible.guardrails.salvage_new_tests` (protocol_version 3) prunes individual tests that pass
collection/compile but fail on the pristine module — a wrong-oracle test, not a bad file — instead
of rejecting the whole file. Every drop is logged per round (`dropped_tests`), never counted as a
kill anywhere in this document. **16 tests were dropped this way across the counted cells:**

| Subject | Arm | Dropped tests |
|---|---|---|
| graph-guard | loop-same | `test_ppr_symmetric_graph_seeded_toward_a` |
| rag-guard | loop-cross | `test_redact_pii_card_with_spaces` |
| packaging | loop-cross | `test_32bit_lsb_with_interpreter`, `test_interpreter_is_read_from_the_pt_interp_program_header`, `test_program_header_file_size_is_interpreted_as_unsigned` |
| idna | loop-same | `test_convert_one_decode_success`, `test_convert_one_encode_success`, `test_main_decode_inferred_from_alabel`, `test_main_encode_unicode_snowman`, `test_main_explicit_encode_overrides_alabel_look`, `test_main_multiple_domains_mode_from_first`, `test_main_reads_from_stdin`, `test_convert_one_encode_forwards_uts46_false`, `test_main_strict_flag_disables_uts46_mapping` |
| attrition-risk-ml | loop-cross | `test_run_builds_expected_pipelines_selects_best_and_persists_outputs`, `test_evaluate_uses_five_explicit_stratified_folds_and_computes_metrics` |

idna's `loop-same` round 0 alone dropped 9 tests in a single round — the largest single-round
salvage event in the counted set, all from the tester's initial CLI-behavior test file computing
wrong expected values against `idna`'s actual encode/decode/stdin conventions. This is exactly the
class of "wrong assumed convention, not a bad test file" case the protocol_version-3 amendment was
built to handle without discarding the file's other, valid tests — the salvage mechanism worked as
designed rather than losing 9 good tests' worth of file alongside them (that file still contributed
kills at round 0, per the full cell table above).

## Instrument-repair narrative

Three silent-corruption incidents were caught before or during the H1/H2 grid — each a case where
the harness would otherwise have recorded a plausible-looking but wrong measurement with **no
error at all**, as opposed to the loud config crashes (missing `pyproject.toml`, dirty clone,
stale `testpaths`) that PROTOCOL.md's earlier amendments (v2-v4) already fixed. Full detail in
`experiments/DEVIATIONS.md` and `PROTOCOL.md` §3.2's amendment notes; summarized here because
RESULTS.md's own numbers depend on them having been fixed before the counted cells ran.

1. **Trampoline crash laundered as a false zero-coverage baseline (protocol_version 5,
   attrition-risk-ml).** A generated test passed on the pristine module and passed a
   pristine-tree confirmatory check, but crashed `mutmut`'s own sandbox trampoline
   (`AssertionError: Failed trampoline hit. Module name starts with 'src.'`) the instant it
   called a real function through mutmut's wrapped import. The pre-existing zero-coverage
   detector could not distinguish this crash from a genuine empty suite and recorded
   `{"killed": 0, "survived": 255}` with `status: "ok"` — no error, no signal, a plausible number
   that was simply wrong. **Fail-closed gate:** `crucible.engine.MutmutEngine.measure` now tees
   `mutmut run`'s stdout/stderr and raises `SandboxStatsFailure` on any non-empty-suite failure
   signature, checked *before* the zero-coverage path runs. Two paid cells ($1.001421) were
   reclassified INSTRUMENT-INVALID and excluded from this document's counted set
   (`DEVIATIONS.md`, row 24).
2. **`pytest_args` include-list silently excluding every freshly generated test from collection
   (protocol_version 6, rag-guard).** A scope naming exactly one file
   (`pytest_args: ["tests/test_guard.py"]`) is an include-list to mutmut's stats-collection
   pytest invocation, not an additional filter: the generated `tests/crucible_*_test.py` file sat
   on disk, correctly copied in, and was simply never asked for. `mutmut` completed **normally**,
   with a real, internally consistent killed/survived split (`kills: []` every round,
   byte-identical baseline-to-round-3 counts) — no error marker of any kind, structurally
   invisible to mechanism #1's stdout-scan detector. **Fail-closed gate:** scopes converted to
   exclude-form (`--ignore=...`), plus a new **canary must-kill probe**
   (`experiments/validate_scopes.py`) that writes a hand-verified test, confirms it passes
   pristine, then asserts the measured kill count *strictly increases* once mutmut actually runs
   it — proving collection, not just import success. Two paid cells ($0.483813) were reclassified
   INSTRUMENT-INVALID (`DEVIATIONS.md`, row 25/27).
3. **The identical include-list mechanism, independently confirmed for a second subject
   (protocol_version 6, graph-guard).** graph-guard's counted H1 cells carried the same
   single-file `pytest_args` shape as rag-guard's. This was flagged as an **open concern, not
   assumed**, then settled by direct reproduction: the canary probe run against the *old* scope
   showed 58→58 killed (no-kills, delta 0) even with the canary file sitting untouched in the
   sandbox; the same probe against the *new* exclude-form scope showed 58→63 (delta +5) on the
   identical clone and mutant population. The config flip alone flipped the outcome, proving —
   not merely suspecting — that graph-guard's original counted cells were instrument-invalid. Two
   paid cells ($0.816747) were reclassified (`DEVIATIONS.md`, row 26/28); graph-guard's *current*
   counted cells in this document are the fresh reruns made after this fix.

All three mechanisms were caught before this document's numbers were computed, by fail-closed
gates that either raise loudly (mechanism 1) or require a positive, measured proof of collection
before trusting a scope (mechanisms 2-3) — never by trusting a plausible-looking zero.

## Limitations

Restated verbatim from PROTOCOL.md §8, still binding:

- **Training-data contamination.** All five subjects are public (or public-facing) repositories;
  the tester/critic models may have seen the exact module during pretraining. The mutant-kill
  metric blunts but does not eliminate this — a memorized suite still has to target the *injected*
  mutant to count as a kill — but the risk is not zero.
- **Mutant-environment detection by hostile tests is not closable without sandboxing.** No syscall
  sandbox is used (spec §10, out of scope); existing guardrails (add-only, pristine-validity,
  flake check, anti-weakening) reduce but do not eliminate this class of gaming.
- **2-run flake check.** A test flaky ~1/3 of the time clears the 2-run check ~4/9 of the time; a
  more expensive N-run check was not adopted.
- **Single tester model.** The Tester is `claude-sonnet-5` in every arm/subject; this design
  measures the *Critic's* lineage effect (H2) holding the Tester fixed. No claim is made about a
  different Tester lineage.
- **idna's `cli.py` reads stdin in `main()`**, a live-input path mutmut's static mutation and
  pytest's collection never execute.
- **attrition-risk-ml's pinned module (`origin/main`, 202 lines) differs from its unmerged
  `fix/calibration` feature branch (284 lines, adds `CalibratedClassifierCV`).** This document
  scores only the pinned `origin/main` version.

New limitations surfaced by this analysis, not in the original §8 list:

- **Single-run design means H1's per-subject picture and H2's per-subject picture are each driven
  by a small number of subjects, not five independent replications.** H1's pooled significance is
  dominated by idna (64 of 79 pooled discordant loop-same-only kills); H2's is dominated by
  attrition-risk-ml and packaging, with rag-guard and idna contributing a hard ceiling-effect zero.
  A single run per cell (§7, "no early stopping ... no re-running") means this concentration
  cannot be distinguished from a genuinely subject-dependent effect versus one-off noise in this
  design; a replication with repeated cells per subject would be needed to separate the two, out
  of scope here.
- **H2's attrition-risk-ml result is confounded with critic-round rejection/format-compliance
  differences, not purely mutant-quality differences.** As detailed above, a material share of the
  same-lineage-vs-cross-lineage kill gap on this subject traces to the same-lineage critic's
  rounds being rejected (one on response format, one on pristine validity) rather than to the
  cross-lineage critic writing categorically harder-to-kill tests. The mechanical oracle correctly
  scores this as zero same-lineage kills either way (§6), but a reader interpreting the *size* of
  H2's effect as "cross-lineage finds better mutants" specifically should discount this subject's
  contribution accordingly.
- **A missing H2 cell (graph-guard) reduces H2's pooled subject count from five to four**, which
  PROTOCOL.md's stopping rules (§7, "exactly once per subject... no re-running") do not provide a
  mechanism to backfill within this pre-registered run. This is disclosed as a real, unplanned-for
  reduction in H2's evidentiary base, not smoothed over.

## Total spend

Computed by `experiments/analyze.py::total_spend`, summing every `result.json`'s
`total_cost_usd` under `experiments/runs/` (never estimated):

| | Total | Receipts |
|---|---:|---:|
| **Counted cells only** | **$4.573085** | 15 |
| All receipted runs (counted + shakeout) | $7.775246 | 27 |
| Shakeout-only (receipted) | $3.202161 | 12 |

**One additional gap, disclosed, not filled in:** `DEVIATIONS.md` (row for `packaging`
`oneshot`/`loop-same`, both crashed before any receipt could be written — `SubjectEnv
.write_test_file` hit `FileNotFoundError` on a missing `tests/` dir, after the tester model had
already been called and billed) records an **estimated** ~$0.21 of real, unreceipted spend across
two crashed attempts. That figure is DEVIATIONS.md's own estimate, not something this script can
recompute from a receipt file — no `result.json` exists for those two attempts — so it is reported
here as a known, bounded gap in the "all receipted" total above, not folded into it. The true total
spend across every model call ever made for this project (counted + shakeout + unreceipted) is
therefore **~$7.99**, of which the ~$0.21 unreceipted portion is an estimate from `DEVIATIONS.md`,
not a receipt-derived figure.

## Summary

| Hypothesis | Verdict | Pooled-with-attrition p | Pooled-without-attrition p | Direction |
|---|---|---:|---:|---|
| H1 (loop-same vs oneshot) | **SUPPORTED** | 3.402e-18 | 2.804e-16 | favors loop-same, both views |
| H2 (loop-cross vs loop-same) | **SUPPORTED, with caveat** | 9.496e-66 | 4.657e-10 | favors loop-cross, both views, but concentrated in 2 of 4 scored subjects and partly confounded by same-lineage critic rejections on attrition-risk-ml |

Neither result is a clean, uniform, five-subject sweep — H1's per-subject picture is genuinely
mixed (3 favor, 1 tie, 1 against) even though the pre-declared pooled statistic clears the bar, and
H2 lost one subject entirely (graph-guard, missing cell) and gets its strongest signal from a
subject whose same-lineage critic rounds were rejected rather than out-competed on merit. Both
are reported here with that texture attached, per PROTOCOL.md §5's instruction that a
non-significant, reversed, or nuanced result gets the same prominence as a clean one.
