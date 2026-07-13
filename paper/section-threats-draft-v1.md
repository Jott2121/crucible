# Threats to Validity — LOCKED (v2; Jeff read + approved 2026-07-13; Fable-verified lockable)

> Staged in scratchpad, NOT committed. No em-dashes. Organized in the standard SE four-way
> (construct / internal / external / statistical-conclusion). Every threat traces to a frozen
> source in the RECEIPTS block. Nothing invented; where a threat is only partly mitigated, it is
> stated as such, matching the frozen limitations.

---

## 7. Threats to Validity

### 7.1 Construct validity

The oracle measures mutant kills, which is a proxy for fault detection, not fault detection itself.
Two gaps follow. First, we perform no equivalent-mutant detection, so some counted survivors may be
semantically equivalent to the original and unkillable by any test; every reported kill rate is
therefore a lower bound. This does not distort the paired comparisons, because both arms in any
comparison face the identical mutant set and an unkillable mutant falls in the both-miss cell that
McNemar discards, but it does mean absolute kill rates should be read as floors. Second, we do not
run generated tests inside a syscall sandbox, so a sufficiently adversarial generated test could in
principle detect properties of the mutation harness itself (timing, file paths, environment
markers) and pass or fail on that rather than on the mutant's behavior. Our guardrails (add-only
tests, pass-on-pristine validation, a flake check, and wrong-oracle pruning) reduce this but do not
mechanically close it. A third construct threat concerns the cost measure: cost-per-kill does not
isolate lineage, because the same-lineage critic's cost is dominated by its output verbosity rather
than its lineage, so the cross-arm cost gap reflects model output style as much as the critic
mechanism.

### 7.2 Internal validity

The H2 comparison carries a confound we disclose where the arms are defined (Section 3.2): each arm
independently regenerates its own round-0 tester suite, so loop-same and loop-cross differ in both
the tester draw and the critic lineage, and a single-run tester draw carries substantial variance
(the same tester produced round-0 kill counts of 69, 168, 50, 62, and 65 across repeated attempts
on one subject). A small cross-lineage difference could therefore reflect tester noise rather than
lineage; a cleaner design would share one frozen round-0 survivor set across both critic arms.

The study's central internal-validity event is the instrument artifact analyzed in Section 5: an
output cap that silently truncated the verbose same-lineage critic and manufactured a large false
H2 effect before it was caught and corrected. We report it as a finding rather than hiding it, but
one residual remains: truncation is mechanically detected only for the provider that declares an
output cap, so a server-side truncation on the other provider would still be laundered. We have no
evidence any occurred (every accepted cross-lineage round is far from any plausible cap), but the
detection asymmetry is structural. A further, smaller asymmetry: one subject's missing-cell rerun
attempts ran with an added parallelism-control configuration that its other two arms did not,
because that configuration was introduced to fight a deadlock; the kill oracle is a deterministic
pass or fail with no channel from a parallelism backend to a verdict, but the instrument
configuration across that subject's arms is not byte-identical, and we record it. Finally, all five
subjects are public code that the models may have seen in pretraining; the mutant-kill metric blunts
but does not eliminate contamination, since a memorized suite would still have to target the
injected mutant to score a kill.

### 7.3 External validity

The strongest limits are on generalization. One cell, the same-lineage-loop arm of the largest
subject (255 baseline survivors), failed to produce a valid verdict within the pre-committed attempt
budget, and the fixed once-per-subject design has no backfill mechanism, so that subject is dropped
from both hypotheses entirely and the pre-declared with-degenerate and without-degenerate pooled
views collapse to a single four-subject composition; the miss is disclosed, not smoothed over. The
remaining paired statistics therefore span four subjects, of which three are the authors' own public
repositories, a convenience sample; the study is single-language (Python) and holds a single tester
model fixed across all arms, so it does not speak to whether a different tester lineage would change
either result. Ceiling effects further
bound what H2 could show: three of the four scorable subjects saturated at 98.6 to 100 percent kill
in both loop arms, leaving no headroom to detect a cross-lineage difference. Two subject-specific
notes also bear on generalization: one subject's target module reads standard input in its
command-line path, which mutation and collection never exercise, and one subject's pinned module
differs from its own development-branch version, so any future run against that branch would be a
different subject, not a rerun.

### 7.4 Statistical conclusion validity

The pooled McNemar test treats individual mutants as independent units, but mutants cluster by
subject (one subject supplies 64 of the 105 H1 discordant pairs), and within-subject correlation is
not modeled; this inflates the nominal pooled significance, which is why per-subject tables are
pre-registered and reported alongside every pooled figure. No a priori power analysis was performed,
and the H2 result is an underpowered null: with so few discordant pairs available, p = 0.0625 is
near the smallest two-sided value the design could produce, so the null means no effect detectable
at this power, never no effect. Kill counts also carry real run-to-run variance from single-run
cells, so per-subject point estimates should be read as noisy; for example, one subject's
same-lineage-loop kills moved from 11 of 22 to 17 of 22 between its invalidated original run and its
valid rerun. And the flake check accepts a test
after it passes on pristine code twice; a test that is flaky roughly one third of the time still
clears a two-run check roughly four times in nine, so some residual flaky-kill noise is expected and
is not separately modeled.

---

## RECEIPTS — claim-to-source (for audit; not part of the paper)

- 7.1 mutant-kill as proxy; no equivalent-mutant detection (lower-bound kill rates); no syscall
  sandbox / mutant-environment gaming; guardrails reduce-not-close -> PROTOCOL.md sec 8 (mutant-
  environment bullet), Method 3.3 (equivalent-mutant note), PROTOCOL sec 6/7 (guardrails).
- 7.2 tester-draw confound + variance 69/168/50/62/65 -> RESULTS.md Limitations ("single-run cells
  are noisy") + Method 3.2. Instrument artifact + detection asymmetry -> RESULTS.md Limitations
  (detection asymmetry) + Discussion 5.2/5.4. attrition cross-arm conftest asymmetry -> RESULTS.md
  Limitations (cross-arm instrument asymmetries) + PROTOCOL v10/v11. Contamination -> PROTOCOL sec 8.
- 7.3 four subjects / three author-owned / single language / single tester -> RESULTS.md Limitations
  + Method 3.3 + PROTOCOL sec 8 (single tester model). Ceiling effects -> RESULTS.md Limitations.
  idna stdin + attrition pinned-module divergence -> PROTOCOL sec 8.
- 7.4 clustering / idna 64-of-105 -> RESULTS.md H1 table + Method 3.5. No power analysis /
  underpowered null / "no effect detectable at this power" -> RESULTS.md H2 + Limitations. Single-
  run variance -> RESULTS.md Limitations. 2-run flake check ~4/9 -> PROTOCOL sec 7/8.

## SELF-CHECK NOTE
All figures here (four subjects, 98.6-100% ceiling, tester variance 69/168/50/62/65, idna 64-of-105,
2-run flake ~4/9) are drawn from frozen sources already grep-verified in prior sections. No new
numbers introduced. To re-confirm at assembly: grep RESULTS.md Limitations + PROTOCOL sec 8 for each.

## CHANGELOG v1 -> v2 (keyed to Fable finding IDs)

- BLOCKING-1 fixed: added the cost-per-kill verbosity confound to 7.1 (construct validity) -- the
  one disclosed limitation (RESULTS Limitations 319-321) the v1 draft silently dropped.
- SHOULD-FIX-2 fixed: 7.3 missing-cell now states the largest-subject drop (255 survivors), the
  no-backfill design, and the collapse of the with/without-degenerate pooled views to one
  composition (RESULTS Limitations 297-300).
- SHOULD-FIX-3 fixed: 7.4 adds the second frozen variance example (graph-guard loop-same 11/22 ->
  17/22 between invalid original and valid rerun, RESULTS Limitations 305-306).
- Fable's 3 rulings all match my leans and are kept: Threats stays its own named Section 7; full
  four-way depth retained; four-way construct/internal/external/statistical structure kept.

## OPEN QUESTIONS
None outstanding. Fable ruled v1 lockable-conditional-on-BLOCKING-1; all three fixes now folded.
