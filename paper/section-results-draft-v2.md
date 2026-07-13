# Results — LOCKED (v2 + grammar nit; Jeff read + approved 2026-07-12; Fable-verified lockable)

> Staged in scratchpad, NOT committed. No em-dashes. Every number traces to frozen
> experiments/RESULTS.md. CHANGELOG (keyed to Fable finding IDs) and RECEIPTS at the bottom.
> The deep autopsy mechanism, the fail-loud repair, and the general lesson are the Discussion;
> this Results section reports the numbers and states the artifact finding at results level.

---

## 4. Results

Every figure below is recomputed from the committed per-run receipts by the analysis script,
driven by a committed manifest of which runs count. This analysis supersedes an earlier one: a
final adversarial review of the completed analysis found a truncation defect sitting inside the
counted cells (an output cap with no truncation detection), which reclassified four counted cells
as instrument-invalid and confounded the entire H2 readout. The version reported here is computed
from the corrected instrument with the affected cells rerun. The headline difference is itself the
paper's central finding: H2's previously significant result did not survive the correction, and
the Discussion analyzes why.

### 4.1 Counted cells

The design is five subjects times three arms, fifteen cells. Fourteen produced valid verdicts;
one, attrition-risk-ml loop-same, is a missing cell, after its original run was reclassified
instrument-invalid and four rerun attempts each failed on a nested-parallelism deadlock that
survived three targeted, individually verified instrument fixes, exhausting the pre-committed
attempt budget. Kill counts are per mutant over each subject's own pristine-baseline survivor set.
The verdict column records how each run terminated: oneshot (baseline, no critic round); clean
(all baseline survivors killed); dry (two consecutive rounds killed nothing new); rounds-cap
(reached the four-round limit); missing (no valid verdict within the attempt budget). Dropped
counts wrong-oracle tests pruned across all rounds and never credited as kills.

| Subject | Arm | Verdict | Baseline survivors | Killed | Rate | Cost ($) | Dropped |
|---|---|---|---:|---:|---:|---:|---:|
| graph-guard | oneshot | oneshot | 22 | 12 | 54.5% | 0.13 | 0 |
| graph-guard | loop-same | dry | 22 | 17 | 77.3% | 1.02 | 1 |
| graph-guard | loop-cross | clean | 22 | 22 | 100.0% | 0.35 | 3 |
| rag-guard | oneshot | oneshot | 25 | 21 | 84.0% | 0.06 | 0 |
| rag-guard | loop-same | clean | 25 | 25 | 100.0% | 0.11 | 0 |
| rag-guard | loop-cross | clean | 25 | 25 | 100.0% | 0.16 | 1 |
| packaging | oneshot | oneshot | 69 | 36 | 52.2% | 0.11 | 0 |
| packaging | loop-same | rounds-cap | 69 | 68 | 98.6% | 0.64 | 0 |
| packaging | loop-cross | dry | 69 | 68 | 98.6% | 0.30 | 3 |
| idna | oneshot | oneshot | 187 | 123 | 65.8% | 0.12 | 0 |
| idna | loop-same | clean | 187 | 187 | 100.0% | 0.65 | 9 |
| idna | loop-cross | clean | 187 | 187 | 100.0% | 0.19 | 0 |
| attrition-risk-ml | oneshot | oneshot | 255 | 62 | 24.3% | 0.07 | 0 |
| attrition-risk-ml | loop-same | missing | 255 | n/a | n/a | 0.07 | 0 |
| attrition-risk-ml | loop-cross | rounds-cap | 255 | 254 | 99.6% | 0.34 | 2 |

Costs are shown to two decimals for readability; the aggregate figures in Section 4.5 are computed
from the full-precision receipts, so summing the rounded column will not exactly reproduce them.
Nineteen wrong-oracle tests were pruned across the fourteen valid cells (nine of them in idna
loop-same alone), each logged and never counted as a kill.

Because attrition-risk-ml's loop-same cell is missing, that subject contributes no paired data to
either hypothesis, so all paired statistics below span the remaining four subjects. The
pre-declared pooled-with-degenerate and pooled-without-degenerate views therefore coincide in
composition for this dataset, a degeneracy we disclose rather than smooth over.

### 4.2 H1 (replication): does the loop kill more than one-shot?

Pre-written support criterion (fixed before any run): H1 is supported if and only if the pooled
McNemar test comparing loop-same to oneshot yields p < 0.05 and the direction favors loop-same
(b > c, where b counts mutants killed by loop-same only).

Per-subject paired 2x2, over each subject's baseline survivor set:

| Subject | both | b (loop-same only) | c (oneshot only) | neither | p (exact McNemar) |
|---|---:|---:|---:|---:|---:|
| graph-guard | 12 | 5 | 0 | 5 | 0.0625 |
| rag-guard | 21 | 4 | 0 | 0 | 0.125 |
| packaging | 36 | 32 | 0 | 1 | 4.66e-10 |
| idna | 123 | 64 | 0 | 0 | 1.08e-19 |

Pooled (confirmatory view): b = 105, c = 0, p = 4.93e-32.

Verdict: H1 SUPPORTED. The pooled p is far below 0.05 and the direction favors loop-same. The
sharper statement is the discordant split itself: across 303 paired baseline survivors in four
subjects, not one mutant was killed by one-shot generation but missed by the loop. Two subjects
individually clear p < 0.05 (packaging, idna) and two do not (graph-guard at 0.0625, rag-guard at
0.125, both with small discordant counts), but the direction is consistent in all four. The pooled
test treats mutants as independent when they in fact cluster by subject, which inflates the nominal
pooled significance; the pool is also idna-heavy (64 of the 105 discordant kills) and
packaging-heavy (32 of 105). We therefore report the per-subject tables alongside the pool rather
than resting on the pooled figure.

Notably, the instrument correction strengthened H1. Under the defect-affected instrument the H1
split read b = 79, c = 5, with one subject tied and one point against the loop. The truncation
defect had been silently removing critic rounds that loop-same should have run, suppressing the
loop's own kills. Correcting it moved packaging from a 4-to-4 tie to plus 32 and graph-guard from
0-versus-1-against to plus 5 (one accepted critic round of over 30,000 output tokens, impossible
under the old cap, killed 5 survivors). The defect worked against H1's own hypothesis, so the true
effect could only be as large or larger than the defect-affected data showed.

### 4.3 H2 (novel claim): does a cross-lineage critic kill more than a same-lineage critic?

Pre-written support criterion: H2 is supported if and only if the pooled McNemar comparing
loop-cross to loop-same yields p < 0.05 and the direction favors loop-cross. A null was
pre-declared to be reported with the same prominence as a positive result.

Per-subject paired 2x2:

| Subject | both | b (loop-cross only) | c (loop-same only) | neither | p (exact McNemar) |
|---|---:|---:|---:|---:|---:|
| graph-guard | 17 | 5 | 0 | 0 | 0.0625 |
| rag-guard | 25 | 0 | 0 | 0 | 1.0 (no discordant pairs, ceiling) |
| packaging | 68 | 0 | 0 | 1 | 1.0 (no discordant pairs) |
| idna | 187 | 0 | 0 | 0 | 1.0 (no discordant pairs, ceiling) |

Pooled (confirmatory view): b = 5, c = 0, p = 0.0625.

Verdict: H2 NOT SUPPORTED. The pooled p of 0.0625 does not clear the pre-registered 0.05 bar. The
point direction favors loop-cross (all five discordant pairs, from the single subject graph-guard,
go the cross-lineage way, and none go the other way), but the evidence does not meet the
pre-written criterion. This is an underpowered null, not a demonstration of no effect: three of
the four scorable subjects saturated at 98.6 to 100 percent kill in both loop arms, leaving zero
discordant pairs, so the design had almost no room to detect a cross-lineage difference even if one
exists. The correct reading is no effect detectable at this design's power, with a directionally
positive but non-significant residual on one subject.

### 4.4 The load-bearing finding: H2's earlier signal was an instrument artifact

Reported at the same prominence as any supported result, because it is the paper's central
contribution. The superseded analysis reported H2 SUPPORTED at a pooled p of 9.5e-66, with b = 217
and c = 0, an apparently overwhelming cross-lineage effect. The corrected instrument erased
essentially all of it.

- packaging: b went from 32 to 0. The old loop-same cell's two critic rounds had both been
  silently truncated at exactly 16,000 output tokens each and rejected under unrelated-sounding
  notes, crediting zero kills. Rerun with truncation detection and a raised cap, the same-lineage
  critic's rounds were accepted and killed 32 more survivors, landing at 68 of 69, identical to
  loop-cross. The strongly supported reading is that the cap deleted the verbose model's rounds;
  because this rests on a single rerun of a cell class that carries real run-to-run variance,
  tester-round variance as a partial contributor cannot be fully excluded by the receipts, so this
  is the well-supported reading rather than a mechanical decomposition.
- attrition-risk-ml: b went from 185 to excluded. Its old loop-same cell was likewise truncation
  invalidated, and the subject could not produce a valid replacement within the attempt budget, so
  the missing-cell rule removed it from the comparison entirely.
- What remains is graph-guard's b = 5, a real gap between two accepted runs worth noting
  descriptively, and three subjects at or near ceiling with no discordant pairs at all.

Stated plainly: the dramatic cross-lineage effect this experiment appeared to measure was
manufactured by a lineage-correlated instrument failure and does not survive the instrument's
correction. The output cap sat on every call to the same-provider model, so it truncated the
verbose same-lineage critic and some tester rounds alike, never the terse cross-lineage critic;
the bias it injected into H2 specifically ran through the same-lineage critic rounds, which is what
manufactured the apparent cross-lineage gap. The Discussion analyzes the mechanism, the fail-loud
repair, and why this generalizes to any cross-model comparison run through an asymmetric harness.

### 4.5 Cost per kill

Aggregated across counted cells with valid verdicts (total cost summed and divided by total kills
summed per arm, from full-precision receipts, never averaged as a per-subject ratio):

| Arm | Total cost ($) | Total killed | Aggregate $/kill |
|---|---:|---:|---:|
| oneshot | 0.4844 | 254 | 0.0019 |
| loop-same | 2.4170 | 297 | 0.0081 |
| loop-cross | 1.3293 | 556 | 0.0024 |

One asymmetry must be read alongside the 3.4-times gap between loop-cross and loop-same: the
oneshot and loop-cross aggregates each span all five subjects, while loop-same spans only its four
valid cells (the missing attrition-risk-ml cell). loop-cross's 556 kills therefore include
attrition-risk-ml's 254, which loop-same never reached, so the arms are aggregated over different
subject sets and the ratio is not a like-for-like per-subject comparison.

With that caveat, the loop-cross arm is about 3.4 times cheaper per kill than loop-same, and the
instrument correction changed the reason. In the superseded analysis the gap was largely
same-lineage dollars spent on truncation-rejected rounds that credited zero kills. With truncation
fixed, the residual gap reflects output-length economics: the same-lineage critic writes long
replies (up to roughly 30,000 output tokens per accepted round, billed at $15 per million output
tokens) while the cross-lineage critic writes terse replies (a few hundred to a few thousand output
tokens per accepted round) at a similar rate card. The honest reading is that verbosity, not
lineage capability, is the dominant cost variable between these two critics. To our knowledge this
per-outcome cost figure is the first reported in the LLM test-generation literature.

---

## CHANGELOG v1 -> v2 (keyed to Fable finding IDs)

- BLOCKING-1 fixed: 4.4 packaging bullet restores the frozen caveat (single rerun cannot fully
  separate the cap's effect from this cell class's known tester-round variance); "strongly
  supported reading," not mechanical fact.
- SHOULD-FIX-2 fixed: 4.5 discloses the cost-arm subject-set asymmetry (loop-same 4 cells excludes
  attrition; loop-cross 5 cells includes attrition's 254 kills), so the 3.4x is not read as
  like-for-like.
- SHOULD-FIX-3 fixed: 4.4 no longer says the cap truncated "only the verbose same-lineage critic";
  it now states the cap sat on every same-provider call (critic and some tester rounds) and scopes
  the H2-specific bias to the critic side.
- SHOULD-FIX-4 fixed: 4.1 verdict terms defined in prose; the max-rounds verdict renamed from "cap"
  to "rounds-cap" to kill the collision with the 4.4 "output cap" truncation term.
- SHOULD-FIX-5 fixed: 19 wrong-oracle drops reported in 4.1 prose; the Dropped column restored.
- SHOULD-FIX-6 fixed: 4.2 restates the clustering/independence caveat inline.
- SHOULD-FIX-7 fixed: 4.2 cut the redundant "never lost a single disagreement" editorial line, kept
  the substantive "not one mutant killed by one-shot but missed by the loop."
- Q2 (rounding): kept 2-decimal display, added the "summing the rounded column will not reproduce
  4.5" note, kept $/kill at 4 decimals.
- Q3 (columns): restored Dropped column, left per-cell $/kill out (redundant with 4.5, noisy on
  tiny cells), per Fable's ruling.

## RECEIPTS — claim-to-source traceability (all from frozen RESULTS.md unless noted)

- 4.0 supersession -> RESULTS.md intro. 4.1 cell table + verdicts + 14-valid/1-missing ->
  RESULTS.md Full cell table + Counted cells. 4.1 verdict-term definitions -> PROTOCOL.md sec 7
  (dry_rounds/max_rounds) + RESULTS verdict column. 4.1 nineteen drops (9 in idna loop-same) ->
  RESULTS.md Wrong-oracle drops.
- 4.2 H1 2x2 + pooled (105/0/4.93e-32) + 303 survivors + b79/c5 strengthening + 30,305-token round
  + idna 64/105 -> RESULTS.md H1 section. Clustering caveat -> Method 3.5 (Fable S6/S2).
- 4.3 H2 2x2 + pooled (5/0/0.0625) + ceiling + "no effect detectable at this power" -> RESULTS.md
  H2 section + Limitations.
- 4.4 old 9.5e-66/b217; packaging 32->0 WITH variance caveat; attrition 185->excluded; graph-guard
  b=5; cap on every Anthropic call incl tester (graph-guard loop-cross round-0 tester) ->
  RESULTS.md load-bearing finding + PROTOCOL.md v9 truncation table.
- 4.5 cost table (0.4844/254/0.0019; 2.4170/297/0.0081; 1.3293/556/0.0024); subject-set asymmetry
  (loop-same 4 cells, oneshot/loop-cross 5; loop-cross includes attrition 254); 3.4x;
  verbosity-not-lineage; first-in-literature -> RESULTS.md Cost-per-kill.

## OPEN QUESTIONS (Fable ruled; Jeff can override)

Fable's rulings on the three v1 questions were applied: (Q1) keep 4.4 lean but the packaging
variance caveat stays here because it is the epistemic status of the number, not mechanism; (Q2)
keep 2-decimal display with the full-precision note; (Q3) restore the Dropped column, leave
per-cell $/kill out. If you disagree with any of these three, say so and I will flip it.
