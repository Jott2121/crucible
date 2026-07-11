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

**This document supersedes the analysis committed at `aa1a059`.** That version was computed
before a final adversarial review found a truncation defect sitting inside the counted cells
(the `max_tokens=16000` cap with no truncation detection — PROTOCOL.md protocol_version-9
amendment), which reclassified four counted cells INSTRUMENT-INVALID and confounded the entire
H2 readout. The version you are reading is computed from the corrected instrument
(protocol_version 9-11), with the affected cells rerun. The headline difference is itself a
finding: **H2's previously "supported" result (pooled p = 9.5×10⁻⁶⁶) does not survive the
instrument correction — it was manufactured almost entirely by an asymmetric truncation
artifact**, detailed in its own section below.

## Counted cells

Five subjects × three arms = 15 cells, one paired run per subject-module per arm, listed with
justification in `experiments/counted.json`. **14 cells produced valid verdicts; 1 cell
(attrition-risk-ml `loop-same`) is a MISSING CELL** per PROTOCOL.md §6 and the pre-committed
v11 stopping rule, after its original run was reclassified INSTRUMENT-INVALID (truncation) and
four rerun attempts each failed on a nested-parallelism deadlock that survived three targeted,
individually-verified instrument fixes (the full forensic trail — loky pools, then warm OpenMP
pools, then a residual mechanism three fixes could not reach — is in `experiments/DEVIATIONS.md`
and the v9-v11 amendment notes). Every other directory under `experiments/runs/` (17 of the 31
receipted, plus pre-receipt crash dirs) is shakeout, instrument-invalid, or a documented failed
attempt — preserved as evidence, excluded from every metric below.

| Subject | oneshot | loop-same | loop-cross |
|---|---|---|---|
| graph-guard | `oneshot-20260710T191723Z` | `loop-same-20260711T004651Z` | `loop-cross-20260710T225355Z` |
| rag-guard | `oneshot-20260710T192857Z` | `loop-same-20260710T192933Z` | `loop-cross-20260710T194336Z` |
| packaging | `oneshot-20260710T181053Z` | `loop-same-20260710T225759Z` | `loop-cross-20260710T194516Z` |
| idna | `oneshot-20260710T181906Z` | `loop-same-20260710T182018Z` | `loop-cross-20260710T194820Z` |
| attrition-risk-ml | `oneshot-20260710T193041Z` | `loop-same-20260711T040046Z` **(MISSING, §6)** | `loop-cross-20260710T195033Z` |

## Full cell table

Kill counts are per-mutant, over each subject's own pristine-baseline survivor set (round 0's
`survivors_before`, measured before any generated test exists). `rate%` = killed / baseline
survivors, one decimal; `$/kill` = `total_cost_usd / killed` (`n/a` when killed = 0 or the cell
is missing). `dropped` = wrong-oracle tests salvaged away by
`crucible.guardrails.salvage_new_tests` (protocol_version 3) across all rounds — never counted
as a kill. A MISSING cell's receipted rounds are preserved evidence, never rendered as kills;
its `cost` column is its receipted spend.

| Subject | Arm | Verdict | Baseline survivors | Killed | Rate | Cost ($) | $/kill | Dropped |
|---|---|---|---:|---:|---:|---:|---:|---:|
| graph-guard | oneshot | oneshot | 22 | 12 | 54.5% | 0.1265 | 0.0105 | 0 |
| graph-guard | loop-same | dry | 22 | 17 | 77.3% | 1.0181 | 0.0599 | 1 |
| graph-guard | loop-cross | clean | 22 | 22 | 100.0% | 0.3468 | 0.0158 | 3 |
| rag-guard | oneshot | oneshot | 25 | 21 | 84.0% | 0.0553 | 0.0026 | 0 |
| rag-guard | loop-same | clean | 25 | 25 | 100.0% | 0.1073 | 0.0043 | 0 |
| rag-guard | loop-cross | clean | 25 | 25 | 100.0% | 0.1582 | 0.0063 | 1 |
| packaging | oneshot | oneshot | 69 | 36 | 52.2% | 0.1139 | 0.0032 | 0 |
| packaging | loop-same | cap | 69 | 68 | 98.6% | 0.6435 | 0.0095 | 0 |
| packaging | loop-cross | dry | 69 | 68 | 98.6% | 0.2963 | 0.0044 | 3 |
| idna | oneshot | oneshot | 187 | 123 | 65.8% | 0.1232 | 0.0010 | 0 |
| idna | loop-same | clean | 187 | 187 | 100.0% | 0.6482 | 0.0035 | 9 |
| idna | loop-cross | clean | 187 | 187 | 100.0% | 0.1883 | 0.0010 | 0 |
| attrition-risk-ml | oneshot | oneshot | 255 | 62 | 24.3% | 0.0656 | 0.0011 | 0 |
| attrition-risk-ml | loop-same | **MISSING** | 255 | — | n/a | 0.0650 | n/a | 0 |
| attrition-risk-ml | loop-cross | cap | 255 | 254 | 99.6% | 0.3397 | 0.0013 | 2 |

Per PROTOCOL.md §3.1/§4, **attrition-risk-ml's numbers above are absolute (kills and rates for
one arm), never a ratio against another arm** — its 0-kill pristine baseline makes any
relative-improvement figure meaningless by construction. With its `loop-same` cell missing, the
subject contributes no paired data to either hypothesis regardless.

## H1 — replication: does the adversarial loop kill more than one-shot?

> **Pre-written support criterion (PROTOCOL.md §5).** "H1 supported if and only if the pooled
> McNemar test (H1 comparison: `loop-same` vs `oneshot`, discordant pairs across all five
> subjects) yields p < 0.05, and the direction favors `loop-same` (more mutants killed by
> `loop-same` than by `oneshot` among the discordant pairs, i.e. b > c where b = loop-same-only
> kills). Any other outcome ... is not supported." The **pooled-with-attrition** view is fixed as
> the confirmatory statistic; pooled-without-attrition and per-subject are pre-declared companion
> readouts.

**Composition note (required disclosure):** with attrition-risk-ml's `loop-same` cell missing
(§6), both pooled views span the same four subjects (graph-guard, rag-guard, packaging, idna)
and are numerically identical — the with/without-attrition distinction §3.1 pre-declared is
degenerate for H1 in this dataset. The confirmatory label stays on the pooled-with-attrition
view as pre-registered; what changed is its composition, disclosed here and in
`DEVIATIONS.md`, not its definition.

### Per-subject 2×2 (paired over each subject's baseline union)

| Subject | both | b (loop-same only) | c (oneshot only) | neither | p (exact McNemar) | Favors loop-same |
|---|---:|---:|---:|---:|---:|:---:|
| graph-guard | 12 | 5 | 0 | 5 | 0.062500 | Yes |
| rag-guard | 21 | 4 | 0 | 0 | 0.125000 | Yes |
| packaging | 36 | 32 | 0 | 1 | 4.657e-10 | Yes |
| idna | 123 | 64 | 0 | 0 | 1.084e-19 | Yes |
| attrition-risk-ml | — | — | — | — | — | **EXCLUDED — missing loop-same cell (§6)** |

### Pooled views (both pre-declared; identical composition here, see note above)

| View | b | c | p (exact McNemar, two-sided) | Subjects pooled |
|---|---:|---:|---:|---|
| **Pooled-with-attrition (confirmatory)** | 105 | 0 | **4.930e-32** | graph-guard, idna, packaging, rag-guard |
| Pooled-without-attrition (companion) | 105 | 0 | 4.930e-32 | graph-guard, idna, packaging, rag-guard |

### Verdict: H1 SUPPORTED

Pooled p = 4.9×10⁻³² < 0.05 and b = 105 > c = 0 → direction favors `loop-same`. Both criteria of
the pre-written rule are met.

**The corrected instrument strengthened H1, exactly as the v9 amendment's conservative-bias
argument predicted.** Under the defect-affected instrument (superseded analysis, `aa1a059`), H1
read b=79, c=5, with one subject tied and one point-against. Under the corrected instrument,
every scorable subject favors the loop and **c = 0: across 303 paired baseline survivors in four
subjects, not one mutant was killed by one-shot generation but missed by the loop.** The two
subjects whose loop-same critic rounds had been truncation-rejected moved most: packaging from a
4-4 tie to +32 (its un-truncated critic rounds killed 23, 6, and 3 survivors), graph-guard from
0-vs-1-against to +5 (a 30,305-token accepted critic round — impossible under the old 16k cap —
killed 5). The pooled result is still idna-heavy (64 of 105 discordant kills) and packaging-heavy
(32 of 105); per-subject effect sizes remain the honest texture, and two subjects individually
clear p<0.05 while two do not (small discordant counts; direction consistent in all four).

## H2 — novel claim: does a cross-lineage critic kill more survivors than a same-lineage critic?

> **Pre-written support criterion (PROTOCOL.md §5).** "H2 supported if and only if the pooled
> McNemar test (H2 comparison: `loop-cross` vs `loop-same`, discordant pairs across all five
> subjects) yields p < 0.05, and the direction favors `loop-cross` ... Any other outcome is not
> supported; a null here is itself the second publishable finding ... and is reported with the
> same prominence as a supported result."

**Composition note (required disclosure):** attrition-risk-ml is excluded (missing `loop-same`
cell, §6), so both pooled H2 views span the same four subjects and are numerically identical
(same degeneracy as H1, disclosed in `DEVIATIONS.md`). graph-guard — the missing H2 cell in the
superseded analysis — is **recovered** here: its original `loop-cross` cell died to a truncated
tester round misrecorded as a content failure; the v9 rerun completed clean.

### Per-subject 2×2 (paired over each subject's baseline union)

| Subject | both | b (loop-cross only) | c (loop-same only) | neither | p (exact McNemar) | Favors loop-cross |
|---|---:|---:|---:|---:|---:|:---:|
| graph-guard | 17 | 5 | 0 | 0 | 0.062500 | Yes |
| rag-guard | 25 | 0 | 0 | 0 | 1.000000 | No (no discordant pairs — ceiling) |
| packaging | 68 | 0 | 0 | 1 | 1.000000 | No (no discordant pairs) |
| idna | 187 | 0 | 0 | 0 | 1.000000 | No (no discordant pairs — ceiling) |
| attrition-risk-ml | — | — | — | — | — | **EXCLUDED — missing loop-same cell (§6)** |

### Pooled views

| View | b | c | p (exact McNemar, two-sided) | Subjects pooled |
|---|---:|---:|---:|---|
| **Pooled-with-attrition (confirmatory)** | 5 | 0 | **0.062500** | graph-guard, idna, packaging, rag-guard |
| Pooled-without-attrition (companion) | 5 | 0 | 0.062500 | graph-guard, idna, packaging, rag-guard |

### Verdict: H2 NOT SUPPORTED

Pooled p = 0.0625 ≥ 0.05 → the pre-written rule's first criterion fails, and per §5 "any other
outcome is not supported." The point direction favors `loop-cross` (b = 5 > c = 0, all five
discordant pairs from one subject, graph-guard), but the evidence does not clear the
pre-registered bar. Per §5, this null is itself the second pre-declared publishable finding.

### The load-bearing finding: H2's previous signal was an instrument artifact

The superseded analysis reported H2 SUPPORTED at pooled p = 9.5×10⁻⁶⁶ (b = 217, c = 0), driven by
packaging (b = 32) and attrition-risk-ml (b = 185). The corrected instrument erased essentially
all of it:

- **packaging: b = 32 → 0.** The old `loop-same` cell's two critic rounds were both
  truncation-rejected (billed exactly 16,000 output tokens each, recorded under misleading
  notes). Rerun with truncation detection and the 32k cap, the same-lineage critic's rounds were
  accepted and killed 32 more survivors — landing at 68/69, identical to `loop-cross`. The
  "cross-lineage critic demolishes same-lineage" gap on this subject was, in its entirety, the
  cap deleting the verbose model's rounds.
- **attrition-risk-ml: b = 185 → excluded.** Its old `loop-same` cell was likewise
  truncation-invalidated; the subject then could not produce a valid replacement cell within the
  pre-committed attempt budget (the §6 missing-cell rule applies). Note the superseded analysis
  itself flagged this subject's H2 contribution as partly a rejection story rather than a
  mutant-quality story; the correction removed it from the comparison entirely.
- **What remains:** graph-guard's b = 5 (a real 22/22-vs-17/22 gap between accepted runs, worth
  noting descriptively) and three subjects at or near ceiling with zero discordant pairs.

Stated plainly, at the same prominence as any supported result (per §5): **the dramatic
cross-lineage effect this experiment appeared to measure was manufactured by a
lineage-correlated instrument failure — an output cap that silently truncated only the verbose
same-lineage critic — and does not survive its correction.** For the cross-lineage question
itself the honest posture is: no measurable advantage at this design's power, with a
directionally positive but non-significant residual on one subject. A better-powered test needs
subjects with headroom below the ceiling (three of four scorable subjects saturated at 98.6-100%)
and repeated cells per subject.

## Cost-per-kill

Aggregated across counted cells with valid verdicts (`total_cost_usd` summed / `killed` summed
per arm — never averaged per-subject ratio). `oneshot` and `loop-cross` aggregate five cells;
`loop-same` aggregates its four valid cells (the missing attrition cell contributes neither cost
nor kills here; its receipted spend appears in Total spend below):

| Arm | Total cost ($) | Total killed | Aggregate $/kill |
|---|---:|---:|---:|
| oneshot | 0.4844 | 254 | 0.0019 |
| loop-same | 2.4171 | 297 | 0.0081 |
| loop-cross | 1.3293 | 556 | 0.0024 |

The `loop-cross` arm remains cheaper per kill than `loop-same` (~3.4×), but the mechanism
changed with the instrument correction: in the superseded analysis the gap was largely
"same-lineage dollars spent on truncation-rejected rounds that credited zero kills." With
truncation fixed, the residual gap reflects real output-length economics — the same-lineage
critic (claude-sonnet-5) writes long replies (up to 30k output tokens per accepted round, billed
at $15/MTok out), while the cross-lineage critic (gpt-5.6-terra) produces terse replies
(431-3,687 output tokens per accepted round) at a similar rate card. Cost-per-kill is also
inflated for `loop-same` by graph-guard's expensive dry tail (two zero-kill rounds at ~$0.15-0.3
each). Per `docs/RELATED-WORK.md` Claim 2, this per-outcome cost accounting remains, to our
knowledge, the first in this literature (AdverTest reports $0.270/method-run, TestForge
$0.63/file — neither divides by outcome). A fair reading: **verbosity, not lineage, is the
dominant cost variable between these two critics.**

## Wrong-oracle drops

`crucible.guardrails.salvage_new_tests` (protocol_version 3) prunes individual tests that pass
collection but fail on the pristine module — a wrong-oracle test, not a bad file. Every drop is
logged per round (`dropped_tests`), never counted as a kill. **19 tests were dropped across the
14 valid counted cells** (the superseded analysis reported 16 across its counted set; the
composition changed with the reruns):

| Subject | Arm | Dropped tests |
|---|---|---|
| graph-guard | loop-same | `test_two_node_cycle_with_single_seed_analytic_fixed_point` |
| graph-guard | loop-cross | `test_ppr_directed_edge_seed_on_source_node`, `test_missing_adjacency_row_uses_empty_dict_default`, `test_missing_out_sum_entries_are_treated_as_dangling_nodes` |
| rag-guard | loop-cross | `test_redact_pii_card_with_spaces` |
| packaging | loop-cross | `test_32bit_lsb_with_interpreter`, `test_interpreter_is_read_from_the_pt_interp_program_header`, `test_program_header_file_size_is_interpreted_as_unsigned` |
| idna | loop-same | `test_convert_one_decode_success`, `test_convert_one_encode_success`, `test_main_decode_inferred_from_alabel`, `test_main_encode_unicode_snowman`, `test_main_explicit_encode_overrides_alabel_look`, `test_main_multiple_domains_mode_from_first`, `test_main_reads_from_stdin`, `test_convert_one_encode_forwards_uts46_false`, `test_main_strict_flag_disables_uts46_mapping` |
| attrition-risk-ml | loop-cross | `test_run_builds_expected_pipelines_selects_best_and_persists_outputs`, `test_evaluate_uses_five_explicit_stratified_folds_and_computes_metrics` |

(The per-cell `dropped` column in the full cell table is the receipt-derived source of truth;
this table names the tests. idna `loop-same`'s 9-drop round remains the largest single salvage
event, unchanged from the superseded analysis — that cell was not rerun.)

## Instrument-repair narrative

The superseded analysis documented three silent-corruption mechanisms caught before its numbers
were computed (trampoline crash laundered as a zero, protocol_version 5; include-list scopes
silently excluding generated tests, v6, confirmed independently on two subjects). Those stand.
This corrected analysis adds the mechanisms found **after** it — one inside the counted data,
and a failure cascade behind the reruns:

4. **Output-cap truncation, asymmetric by lineage (protocol_version 9).** `max_tokens=16000` on
   every Anthropic call with no truncation detection anywhere. A capped reply was handed to
   validation as ordinary text and rejected under an unrelated-sounding note ("expected exactly
   one fenced python block, found 0"; "invalid: fails on pristine code"). 8 rejected rounds sat
   in the counted cells; 7 of them billed exactly 16,000 output tokens. The verbose same-lineage
   critic hit the cap routinely; the terse cross-lineage critic never did (accepted-round range
   431-3,687 output tokens) — a lineage-correlated artifact that manufactured most of H2's
   apparent signal and conservatively suppressed H1's. Caught not by a runtime gate but by the
   final adversarial review reading the completed analysis. **Fail-closed gate now:**
   `output_cap` is a mechanical ceiling — `env._call` compares every reply's `usage.output_tokens`
   against it and a truncated round is rejected loudly as `"truncated: output hit max_tokens
   cap"`, billed cost metered, raw reply archived. Four counted cells reclassified and rerun.
   Residual, disclosed: the OpenAI provider sends no `max_tokens` and so is never
   truncation-checked — detection exists only where a mechanical cap does.
5. **The rerun failure cascade (protocol_version 10-11, DEVIATIONS.md).** Fixing the cap exposed,
   in sequence: replies long enough to exceed a hardcoded 300s HTTP read timeout (fixed, 1200s);
   an unbounded, receipt-invisible hang when a generated test's own process pool deadlocked
   inside mutmut's forked workers (bounded, `MUTMUT_RUN_TIMEOUT_S=3600` → loud `MeasureTimeout`);
   and, on one subject, a deadlock that survived three targeted fixes (loky eliminated, native
   thread pools pinned) and consumed its pre-committed attempt budget — ending, per the stopping
   rule fixed at approval time, in this document's one missing cell rather than a fifth attempt.

All of it is receipted: every failed attempt's partial receipts are committed, every
reclassification has a DEVIATIONS row, and the stopping rule was written down before the final
attempt ran.

## Limitations

Binding limitations from PROTOCOL.md §8 (training-data contamination; no syscall sandbox against
mutant-environment gaming; the 2-run flake check; single tester model; idna's stdin path;
attrition-risk-ml's pinned-module divergence from its feature branch) all still apply. New or
sharpened by this analysis:

- **One missing cell (attrition-risk-ml loop-same) removes the largest subject from both
  hypotheses' paired statistics**, and makes the pre-declared pooled-with/without-attrition
  distinction degenerate (identical four-subject composition). §7's "exactly once per subject"
  design has no backfill mechanism; the miss is disclosed, not smoothed.
- **Ceiling effects cap H2's power.** Three of four scorable subjects saturated at 98.6-100% in
  both loop arms, leaving zero discordant pairs. This design cannot detect a cross-lineage
  effect where there is no headroom; a future test needs harder subjects or deeper survivor sets.
- **Single-run cells are noisy.** The same tester (same subject, same prompt, same model)
  produced 69, 168, 50, 62, and 65 round-0 kills across attrition-risk-ml attempts, and
  graph-guard's loop-same went 11/22 → 17/22 between (invalid) original and (valid) rerun. Kill
  counts carry substantial run-to-run variance; per-subject point estimates should be read
  accordingly, and repeated cells per subject are the obvious next design.
- **Cross-arm instrument asymmetries on attrition-risk-ml, disclosed:** its (missing) loop-same
  attempts ran with the v10/v11 conftest (joblib threading backend, native thread pools pinned
  to 1) while its counted oneshot/loop-cross cells ran without it. The kill oracle is a
  deterministic pass/fail with no channel from a parallelism backend to a verdict; recorded
  because instrument configuration across this subject's arms is not byte-identical (PROTOCOL.md
  v10/v11 amendment notes).
- **Detection asymmetry:** truncation is mechanically detectable only for providers declaring an
  `output_cap` (the Anthropic provider). A server-side truncation on the OpenAI side would still
  be laundered. No evidence any occurred (all accepted GPT rounds are far from plausible caps),
  but the blind spot is structural.
- **The loop-same arm's costs are dominated by output verbosity, not lineage capability** (see
  Cost-per-kill) — cost comparisons between these arms are as much about model style as about
  the critic mechanism.

## Total spend

Computed by `experiments/analyze.py::total_spend`, summing every `result.json`'s
`total_cost_usd` under `experiments/runs/` (never estimated), plus receipted-but-unfinished
spend accounted separately:

| | Total | Receipts |
|---|---:|---:|
| **Counted cells with valid verdicts** | **$4.2307** | 14 |
| Missing cell's receipted spend (in counted.json, no verdict) | $0.0650 | (receipt rows only) |
| All receipted runs (counted + shakeout + invalid) | $9.9078 | 31 |
| Shakeout/invalid/failed-attempt receipted spend | $5.6771 | 17 |

Known unreceipted spend (bounded estimates, DEVIATIONS.md): ~$0.21 from the packaging
`write_test_file` crash pair (pre-v5, unchanged from the superseded analysis) and ~$0.42 from
two attrition rerun attempts whose round-1 critic calls were billed but whose receipt rows never
landed (the measure they awaited deadlocked). True all-in total across every model call ever
made for this experiment: **~$10.5**, of which ~$0.63 is bounded estimate rather than
receipt-derived.

## Summary

| Hypothesis | Verdict | Pooled p (confirmatory) | Direction | One-line honest read |
|---|---|---:|---|---|
| H1 (loop-same vs oneshot) | **SUPPORTED** | 4.930e-32 | favors loop-same, b=105 c=0 | The loop strictly dominated one-shot on every scorable subject under the corrected instrument. |
| H2 (loop-cross vs loop-same) | **NOT SUPPORTED** | 0.062500 | favors loop-cross, b=5 c=0, one subject | The dramatic cross-lineage effect was a truncation artifact; corrected, no measurable advantage at this power. |

H1 is a replication (per `docs/RELATED-WORK.md`, never a priority claim) that got *stronger*
under instrument correction — the defect had been suppressing the loop's own rounds. H2 is the
pre-declared publishable null, plus something the pre-registration did not anticipate but the
receipts force us to report: a worked, fully-receipted case study of a lineage-correlated
instrument artifact manufacturing a p = 9.5×10⁻⁶⁶ "effect" that vanished when the instrument was
fixed. Cross-model comparisons inherit every asymmetry of the harness that runs them; this
experiment now documents, with receipts, exactly how that happens and what it costs to catch it.
