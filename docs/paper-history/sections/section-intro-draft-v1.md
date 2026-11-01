# Introduction — LOCKED (v2; Jeff read + approved 2026-07-13; Fable final-verified lockable, no drift)

> Staged in scratchpad, NOT committed. No em-dashes. The Intro previews the whole paper, so every
> factual claim here restates a locked section (Method/Results/Discussion/Related Work), which in
> turn traces to the frozen sources. RECEIPTS at the bottom. All numbers (105/0, 4.9e-32, 5/0,
> 0.0625, 9.5e-66) are the frozen, grep-verified figures used in the locked Results and Discussion.

---

## 1. Introduction

Large language models now write both production code and the tests meant to check it, and the
second job is the weaker link. Coverage, the usual measure of a test suite, records which lines ran,
not whether anything about their behavior was actually verified, and a model asked to write tests
for its own code tends to take the path of least resistance: it exercises the happy path and asserts
weakly, producing suites that are green and nearly empty of fault-detecting power. A test suite can
be fully covered and catch almost nothing. As models take over more of the testing work, the
evidentiary value of "the tests pass" is arguably falling, precisely where practitioners are relying
on it more.

Mutation testing is the standard way to measure a suite's fault-detecting power directly. It injects
small, deliberate defects (mutants) into the code and counts how many the suite catches: a killed
mutant is a defect the tests detected, and a surviving mutant is a specific, named gap the tests
would let through. We use mutation testing as a mechanical oracle inside a two-role loop. A Tester
model writes an initial suite; the surviving mutants are handed, by name, to a Critic model that
writes tests to kill exactly those; the loop repeats until no new mutants die. Every verdict in this
loop is mechanical: a generated test either kills a mutant under the test runner or it does not, and
no model ever judges its own or another model's output. The design deliberately removes model
judgment from the verdict, which is the channel through which self-preference bias corrupts
model-graded evaluation. Removing model judgment from the verdict is necessary but, as this study's
own experience shows (Section 5), not sufficient to make a cross-model comparison neutral.

We do not claim this loop is new. Feeding survivor mutants back into a model prompt and running an
adversarial test-versus-mutant loop under a mechanical oracle are both established in prior work.
Our study is a pre-registered empirical evaluation, and its value is in the discipline with which it
was run and reported, not in the idea. We froze the hypotheses, the subjects, the measurement
scopes, and the success criteria before any paid run, enforced that freeze in tooling, and required
every reported number to be recomputable from committed per-run receipts. We test two hypotheses on
five pinned Python subjects under the mutation-kill oracle: H1, that the adversarial loop kills more
mutants than one-shot generation; and H2, that a cross-lineage Critic (a different-provider model)
kills more of the survivors a same-lineage Tester missed than a same-lineage Critic does. We report
cost per killed mutant throughout.

H1 is supported and, we argue, is a clean replication of a known effect in a new agentic,
repo-level, Python setting: across the paired mutants where the two approaches disagreed, the loop
killed 105 that one-shot generation missed and lost none, a result that grew stronger, not weaker,
when a measurement defect working against it was corrected. H2 is not supported; it is a
pre-declared and honestly underpowered null, because most subjects saturated at the kill ceiling and
left almost nothing to discriminate on.

The paper's central contribution is neither of those results. It is an account of how this study's
own measurement instrument manufactured a large false result and how that was caught. An earlier
version of the H2 analysis reported an overwhelming cross-lineage effect, a pooled significance of
p = 9.5 x 10^-66. It was almost entirely an artifact. A fixed output
ceiling on one provider's model silently truncated that model's replies, and because the
same-lineage Critic is the verbose model and the cross-lineage Critic is terse, the truncation was
systematically correlated with the exact variable under test. It did not add noise; it manufactured
a difference. The defect produced no crash and no error, only a plausible rejection, and it survived
every mechanical gate in the pipeline; it was caught only by a final adversarial review of the
completed analysis, and when it was corrected the apparent effect collapsed to non-significance. The
general lesson, which this paper documents with receipts, is that a cross-model comparison can
inherit the asymmetries of the harness that runs it: closing the model-judgment channel does not
make the comparison neutral if the apparatus feeding the two models is not itself symmetric.

This paper makes four contributions:

1. A pre-registered replication of the adversarial test-hardening effect (H1) in a new agentic,
   repo-level, Python setting, with per-outcome costs disclosed, an accounting we believe is the
   first of its kind in the LLM test-generation literature.
2. A pre-declared, honestly underpowered null on the cross-lineage Critic question (H2) under a
   mechanical mutation-kill oracle, a comparison we could not find measured in prior work.
3. As the durable contribution, a fully receipted autopsy of a lineage-correlated instrument
   artifact that manufactured an extraordinary false result, together with the fail-closed
   instrumentation that detects and prevents its recurrence, and the general lesson for cross-model
   evaluation that follows from it.
4. A public, reproducible artifact: the pre-registered protocol, the per-run receipts, the
   deviations log, and the analysis script that recomputes every reported statistic.

---

## RECEIPTS — every Intro claim restates a locked section (which traces to frozen sources)

- Para 1 coverage-not-fault-detection, weak-assertion-for-AI-code -> Method 3.1; frozen thesis.
- Para 2 mutation testing / loop / mechanical verdict / no-model-judges-model -> Method 3.1.
- Para 3 "not new" (MuTAP/AdverTest) -> Related Work 6.2/6.3 + Method 3.1. Pre-registration +
  tooling-enforced freeze + receipts -> Method 3.6. H1/H2 statements + cost-per-kill -> Method 3.2/3.7.
- Para 4 H1 supported, 105-to-0, strengthened under correction -> Results 4.2; Discussion 5.1.
  H2 underpowered null, ceiling -> Results 4.3.
- Para 5 old p=9.5e-66 artifact; output-cap truncation; verbosity asymmetry systematic not noise;
  no crash/caught by final review; collapsed to non-significant; general lesson -> Discussion 5.2/5.3;
  Results 4.4.
- Contributions 1-4 -> Method 3.2/3.7 (H1, cost-per-kill), Results 4.3 (H2 null), Discussion 5.2-5.4
  (autopsy + lesson), Method 3.9 (artifacts).

## SELF-CHECK NOTE
Numbers restated: 105 / 0 / (loop never lost) and "grew stronger" (Results 4.2, frozen b=105 c=0
p=4.9e-32; pre-correction b=79 c=5); 9.5e-66 (Results 4.4 / Discussion 5.2, frozen). No new number
introduced; all are the frozen figures already grep-verified in the locked sections.

## CHANGELOG v1 -> v2 (keyed to Fable finding IDs)

- SHOULD-FIX-1: para 2 now signals up front that removing model judgment from the verdict is
  "necessary but ... not sufficient to make a cross-model comparison neutral (Section 5)," defusing
  the self-preference seam explicitly instead of by distance (matches locked Method 3.1 / Discussion 5.3).
- SHOULD-FIX-2: para 1 "is falling" -> "is arguably falling," keeping it clearly a motivating
  premise, not a measured time-trend.
- RULING-1: kept p=9.5e-66 as the Intro hook, rewritten in notation (p = 9.5 x 10^-66) instead of
  spelled out.
- RULING-2: kept C1's "first of its kind in the LLM test-generation literature" with the scope words
  intact (load-bearing; must not drift to a bare "first per-outcome cost accounting").
- RULING-3: length kept (5 paragraphs + 4-item list; each does distinct work, no padding).

## OPEN QUESTIONS
None outstanding; Fable ruled v1 lockable and all three rulings + two should-fixes are applied.
