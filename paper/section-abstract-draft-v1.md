# Abstract — LOCKED (v2; Jeff approved 2026-07-13; Fable ruled lockable; one-clause fix folded)

> Staged in scratchpad, NOT committed. No em-dashes. The Abstract distills the locked Intro and
> restates only what the locked sections establish. It holds the three disciplines Fable flagged as
> the Abstract's highest overclaim risk: H1 = replication (not discovery), H2 = underpowered null
> (never "no effect"), autopsy at the pooled level (9.5e-66 -> non-significant, no packaging-specific
> causal decomposition). ~190 words. RECEIPTS below.

---

## Abstract

Large language models increasingly write both code and the tests meant to check it, and coverage,
the usual measure of a suite, records what ran rather than what was verified. We study an
adversarial test-hardening loop under a mechanical oracle: a Tester model writes tests, mutation
testing names the surviving injected defects, and a Critic model writes tests to kill exactly those,
with every verdict decided mechanically so that no model judges another model's output. In a
pre-registered experiment on five Python subjects (one loop-same cell could not be scored) we test
whether the loop kills more mutants than one-shot generation (H1) and whether a cross-lineage Critic
outperforms a same-lineage one (H2), reporting cost per killed mutant. H1 is supported and is a replication of a known effect in a new
setting: the loop killed 105 mutants that one-shot generation missed and lost none. H2 is a
pre-declared, underpowered null. The central contribution is an autopsy: an earlier analysis
reported a cross-lineage effect at p = 9.5 x 10^-66 that was a lineage-correlated instrument
artifact, an output cap that silently truncated the verbose model, caught only by adversarial review
of the completed analysis and collapsing to non-significance once corrected. We conclude that
cross-model comparisons can inherit the asymmetries of the harness that runs them, and we release the
protocol, receipts, and analysis.

---

## RECEIPTS — every Abstract claim restates a locked section

- "coverage records what ran not what was verified" -> Intro para 1 / Method 3.1.
- loop mechanics + "no model judges another model's output" -> Intro para 2 / Method 3.1.
- pre-registered, 5 Python subjects, H1/H2 statements, cost-per-kill -> Intro para 3 / Method 3.2/3.6/3.7.
- H1 supported, replication, "105 ... lost none" -> Intro para 4 / Results 4.2 (b=105, c=0).
- H2 "pre-declared, underpowered null" -> Intro para 4 / Results 4.3 (p=0.0625; never "no effect").
- autopsy p = 9.5 x 10^-66, lineage-correlated output-cap truncation, caught by adversarial review,
  collapsed to non-significance -> Intro para 5 / Discussion 5.2 / Results 4.4 (pooled level; NO
  packaging-specific causal decomposition).
- "cross-model comparisons can inherit the asymmetries of the harness" -> Discussion 5.3 (matches
  the "can inherit" hedged heading, not the stronger form).
- "release the protocol, receipts, and analysis" -> Method 3.9 / Intro contribution 4.

## DISCIPLINE CHECK (Fable's three highest-risk lines, held)
- H1: "a replication of a known effect in a new setting" -- NOT "discovery." Held.
- H2: "a pre-declared, underpowered null" -- NOT "no effect" / "no difference." Held.
- Autopsy: stated at the pooled level (p=9.5e-66 -> non-significance); NO "packaging's gap became
  0-to-0" causal decomposition. Held.

## CHANGELOG v1 -> v2 (keyed to Fable finding IDs)

- SHOULD-FIX-1 + RULING-3 (one fix, double duty): added "(one loop-same cell could not be scored)"
  to the design clause. This defuses the five-vs-four juxtaposition (the 105/0 result is a
  four-subject figure; the parenthetical stops a reader attaching it to five) AND supplies the
  honest self-limitation signal Fable ruled the Abstract should carry, without a separate
  editorializing clause. "one loop-same cell" is accurate to the frozen missing cell
  (attrition-risk-ml loop-same, RESULTS Counted cells).
- RULING-1: length kept (~190 words; tightening to 150 would force dropping the cost-per-kill or the
  mechanism clause, both load-bearing).
- RULING-2: kept the concrete mechanism clause ("an output cap that silently truncated the verbose
  model") as the autopsy hook.

## OPEN QUESTIONS
None outstanding; Fable ruled v1 lockable and the one should-fix + all three rulings are applied.
