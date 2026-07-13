# Method — LOCKED (v3 + pilot clause; Jeff read + approved 2026-07-12; Fable-verified lockable)

> Staged in scratchpad, NOT committed. No em-dashes. Every claim tagged to its frozen source in
> the RECEIPTS block. Changes from v2 are summarized in the CHANGELOG at the bottom, keyed to
> Fable's finding IDs, plus a short REMAINING-TODO list of facts that must be pulled from the
> repo (not invented) before the paper is final.

---

## 3. Method

### 3.1 The adversarial test-hardening loop

We evaluate a two-role loop over a mechanical mutation-kill oracle. A Tester model is prompted
once to write a pytest suite for a target module (round 0). The suite is run under mutation
testing (mutmut): each surviving mutant is an injected defect the suite failed to catch. A Critic
model is then handed the named survivors, the specific mutants left alive together with their
diffs, and prompted to write tests that kill exactly those. The loop repeats. After each Critic
round the suite is re-measured, newly killed survivors are removed from the target list, and the
next round attacks what remains. A run stops when two consecutive rounds kill nothing new
(dry_rounds = 2) or after four rounds (max_rounds = 4), whichever comes first.

The verdict at the core of this loop is mechanical: a generated test either kills a mutant under
pytest or it does not, and no model ever judges its own or another model's output. This closes
the self-preference channel that undermines LLM-as-judge evaluations, where a model scoring model
output has no ground truth. We are careful not to overstate what this buys. The mechanical oracle
removes model judgment from the verdict itself; it does not make the surrounding measurement
apparatus neutral. Section 5 documents a case where the harness around the oracle opened a
lineage-correlated channel into the result even though the oracle itself never rendered a
subjective judgment.

We do not claim the loop is novel. Feeding survivor mutants into an LLM prompt was established by
MuTAP, and a dual-agent adversarial test-versus-mutant loop under a mechanical oracle was
established by AdverTest. Our contribution is a controlled measurement, described below, and a
fully receipted account of what it took to make that measurement trustworthy (Section 5).

### 3.2 Arms and hypotheses

Each subject module is run through three arms, all sharing one fixed Tester model
(claude-sonnet-5, Anthropic) so that the only deliberate variable is the Critic:

- oneshot: Tester round 0 only, no Critic round. This is the one-shot baseline.
- loop-same: Tester round 0, then Critic rounds where the Critic is the same lineage as the
  Tester (claude-sonnet-5, Anthropic).
- loop-cross: Tester round 0, then Critic rounds where the Critic is a different lineage
  (gpt-5.6-terra, OpenAI).

The cross-lineage Critic is deliberately price- and capability-tier matched to the same-lineage
Critic ($2.50/$15 per million tokens versus $3/$15) rather than paired with the flagship variant,
so that the comparison isolates lineage rather than confounding it with model capability tier. We
pin real model identifiers throughout, rather than anonymizing, because the cost accounting is
tied to specific rate cards and the instrument finding in Section 5 is provider-specific and
cannot be stated without them.

Two hypotheses follow:

- H1 (replication): the adversarial loop (loop-same) kills more mutants than one-shot generation
  (oneshot), holding the Tester model fixed.
- H2 (novel claim): a cross-lineage Critic (loop-cross) kills more of the survivors the
  same-lineage Tester missed than a same-lineage Critic (loop-same) does.

H1 is framed strictly as a replication of the MuTAP-to-AdverTest loop direction in a new
agentic, repo-level, Python setting with disclosed per-outcome costs. H2 is the claim we could
not find measured in prior work: to our knowledge no prior study measures the effect of
critic-generator lineage diversity on test-suite fault detection under a mechanical mutation-kill
oracle. Both directions of the H2 result were pre-declared publishable, including a null, so the
direction was not assumed in our favor.

One design limitation is inherent to these arms and we state it where the arms are defined rather
than burying it later. Each arm independently regenerates its own round 0, so the tester suite
and its resulting survivor set are not held fixed between loop-same and loop-cross. The two
critic arms therefore differ in both the round-0 tester draw and the critic lineage, and
single-run tester draws carry substantial variance (Section 6 reports the same tester producing
round-0 kill counts of 69, 168, 50, 62, and 65 across repeated attempts on one subject). A
cleaner design would freeze one round-0 survivor set and run both critics from that identical
state; this study did not, and any small cross-lineage difference it reports must be read against
that confound.

### 3.3 Subjects and selection

Five Python subjects, each pinned by commit SHA, each contributing one paired subject-module cell
to every arm. Subjects were selected against criteria fixed before selection (recorded in the
pre-registration's selection log). Three are the author's own public repositories and two are
third-party open-source projects; this convenience component is a disclosed threat to external
validity (Section on Threats), compounded by training-data contamination since all five are
public code the models may have seen in pretraining. For each subject exactly one target module
is mutated, and sibling files needed for imports are carried into the mutation sandbox unmutated.
One subject (graph-guard) was pre-declared as a pilot with a go/no-go gate before the full grid,
and its pilot cells were pre-declared to count as data; in the event those cells were later
reclassified for an instrument defect (Section 3.8) and rerun, so the pilot designation does not
affect the counted dataset.

| Subject | Provenance | Target module | Suite | Mutants | Killed by existing suite | Baseline survivors (scored) |
|---|---|---|---|---:|---:|---:|
| attrition-risk-ml | author repo (public) | `src/train.py` | kept | 255 | 0 | 255 |
| graph-guard | author repo (public) | `graph_guard/ppr.py` | kept | 80 | 58 | 22 |
| rag-guard | author repo (public) | `rag_guard/guard.py` | kept | 71 | 46 | 25 |
| packaging | pypa/packaging (OSS) | `src/packaging/_elffile.py` | stripped | 69 | 0 | 69 |
| idna | kjd/idna (OSS) | `idna/cli.py` | stripped | 187 | 0 | 187 |

Both mutation denominators are shown, per the pre-registration's rule that neither the
full-mutant count nor the baseline-survivor count is presented alone. The two third-party
subjects have their existing suites stripped in the local clone before any run, so the loop is
scored against a genuinely empty starting suite and never against the upstream project's own
tests; the three author-repo subjects keep their existing suites, so their scored denominator is
the survivors an already-present suite left alive.

One subject, attrition-risk-ml, is degenerate by design and kept deliberately. Its existing suite
kills 0 of 255 mutants, because the target module is never imported by any test, so it is the
maximal-headroom false-pass case: a suite that looks present but catches nothing, exactly the
failure mode this line of work exists to expose. Because any ratio against a zero-kill baseline
is undefined and any intervention trivially wins against zero, this subject is reported with
absolute kill counts only, never a relative-improvement figure.

We perform no equivalent-mutant detection. Some mutants in each subject may be semantically
equivalent to the original and therefore unkillable by any test, which means every reported kill
rate is a lower bound. This does not affect the paired comparisons: both arms in any comparison
face the identical mutant set, so an unkillable mutant simply lands in the both-miss cell that
McNemar discards.

### 3.4 The mechanical oracle

Mutation testing is run with mutmut, which injects rule-based, single-change mutants (one
mutation per variant), in contrast to LLM-generated mutants used by some adversarial-loop systems.
Each subject's mutation scope, meaning the exact module mutated and the exact sibling files copied
into the sandbox, was fixed at pre-registration and thereafter changed only through logged,
receipted amendments (Section 3.8), never silently at run time. Kills are counted per mutant over
each subject's own pristine-baseline survivor set: round 0's survivors measured before any
generated test exists, so both arms in any comparison are scored against the same universe of
mutants. A generated test that fails to compile, fails on the pristine (un-mutated) module, or
fails a flake check (it must pass on pristine code twice) is rejected before it can contribute a
kill; the rejection and its reason are recorded, and the round credits zero kills. A test that
passes collection but fails on the pristine module, a wrong-oracle test rather than a bad file, is
pruned individually and logged, never counted as a kill.

### 3.5 The paired statistic

Because every arm runs against the same pinned subject clone, kill outcomes are paired
mutant-for-mutant across arms. The primary statistic is a two-sided exact McNemar test on the
discordant pairs: b = mutants killed by arm A only, c = mutants killed by arm B only. Pairs where
both arms agree (both kill, or both miss) carry no information and are excluded by construction;
the evidence lives entirely in the disagreements. The test uses the doubled exact binomial tail
(min-tail doubling, with n = 0 defined as p = 1), not the chi-square approximation, which is
appropriate for the small discordant counts these subjects produce.

The pooled test treats individual mutants as the unit of analysis, which assumes independence
across mutants; in fact mutants are clustered by subject (idna alone contributes 64 of the 105
H1 discordant pairs), and within-subject correlation among mutants of one module is not modeled.
This inflates the nominal pooled significance, which is why we pre-registered per-subject tables
as a companion readout and report them alongside every pooled figure rather than resting on the
pool alone.

Each hypothesis is reported in three pre-declared views, all fixed before any data. First, one
pooled McNemar across all subjects' discordant pairs, designated the confirmatory statistic.
Second, a pooled view excluding the degenerate subject, whose 255 paired outcomes would otherwise
dominate the pool. Third, per-subject McNemar tables. All three views were committed in advance
and all three are reported for both hypotheses, so no view can be chosen, promoted, or dropped
after seeing results. We ran no a priori power analysis; with three of four scorable subjects at
or near a 98.6 to 100 percent kill ceiling, the number of discordant pairs available to H2 was
near its structural minimum, so the H2 null is stated throughout as "no effect detectable at this
design's power," never as "no effect."

### 3.6 Pre-registration, enforced by tooling

The protocol, meaning the hypotheses, arms, subjects, frozen scopes, the exact statistic, and the
supported-or-not-supported criteria, was written and committed before any paid run. The freeze is
not a promise. The experiment command mechanically refuses to run any arm unless the committed
machine-readable protocol is byte-identical to the repository HEAD, and every reported number is
required to be recomputable from committed per-run receipts (the per-round JSON logs recording
token counts, cost, verdicts, and preserved test artifacts for every run). The success criteria
were fixed in advance: H1 is supported if and only if the pooled McNemar yields p < 0.05 and the
direction favors loop-same; H2 if and only if the pooled McNemar yields p < 0.05 and the
direction favors loop-cross. Any other outcome, in either case, is not supported, and a null was
pre-declared to be reported with the same prominence as a positive result. No subgroup analysis
was permitted to substitute for the three pre-declared views; any post-hoc breakdown is labeled
exploratory and never replaces the primary readout.

Each arm runs once per subject under a fixed grid (three arms times five subjects, fifteen cells).
A cell that produces a valid verdict is never rerun in search of a better one, and there is no
early stopping for significance. A cell that is invalidated or aborts may be rerun only under a
logged deviation, and one subject's loop-same cell was attempted five times against a
pre-committed attempt budget; when that budget was exhausted without a valid verdict, the cell was
recorded as missing data rather than backfilled or estimated. Every departure from the frozen
protocol is logged in an append-only deviations file. Fourteen of the fifteen cells produced valid
verdicts; the one missing cell (attrition-risk-ml loop-same) removes the largest subject from the
paired statistics, so all paired analyses span four subjects, and the pre-declared with-degenerate
and without-degenerate pooled views coincide in composition for this dataset (a degeneracy we
disclose rather than smooth over).

### 3.7 Cost accounting

Every model round is metered exactly from its input and output token counts; an unpriced model
fails the run closed rather than pricing at a guessed rate. We report cost-per-kill, meaning total
cost divided by mutants killed, per arm. To our knowledge this per-outcome normalization is not
reported in the LLM test-generation literature, where systems report cost per method-run or per
file; the adjacent defect-discovery literature does report a per-outcome figure (a cross-model
critic system reports a dollar cost per discovered vulnerability), so we scope the novelty to test
generation rather than claiming it broadly.

### 3.8 Instrument integrity

The measurement instrument was itself treated as a subject of scrutiny, and the honest account of
what that surfaced falls into three tiers rather than one.

First, defects caught for free, before any model was called, by a model-free dry-run validator
built partway through the study: scope-transcription errors and a mutation-sandbox failure that
would have silently recorded every mutant as unchecked. From the point that validator existed, and
later a canary must-kill probe that confirms the sandbox actually collects a freshly written test,
each subsequent scope fix was validated by a zero-cost dry run before any further paid cell ran.

Second, and this is the part a paper about instrument honesty must not soft-pedal, defects caught
only after paid cells had already run, which forced reclassification of already-spent data. A
trampoline crash that laundered into a false all-survived zero, and an include-list scoping bug
that silently prevented freshly generated tests from being collected, together invalidated several
paid cells, including two that had previously been counted as data. More was ultimately spent on
runs that were invalidated and rerun than on the runs finally counted. That the instrument had to
throw away paid data is not the embarrassing part; concealing it would be.

Third, the one defect caught only after all fifteen counted cells had run, by a final adversarial
review of the completed analysis rather than by any runtime gate. Because it changed the headline
result, it is documented in full as a finding in its own right (Section 5). In every tier the
repair principle was the same: make the instrument fail loudly rather than record a
plausible-looking wrong number. Across the study the protocol carried ten numbered amendments plus
one prompt-template amendment, each logged with its rationale and its cost consequences.

### 3.9 Reproducibility and disclosure

All counted cells ran under a single fixed prompt version, with one per-subject import hint added
for the subject whose package layout required it; the prompt texts are content-hashed and the
hashes are recorded in the pre-registration. The protocol, the machine-readable arms
configuration, the per-run receipts, the deviations log, and the analysis script that recomputes
the reported statistics are committed to the public repository, so every reported statistic is
reproducible from the receipts. A small, bounded portion of the all-in spend total is disclosed as
an estimate rather than receipt-derived, where a crash billed a call before its receipt row
landed. An automated reproduction command is provided. The manuscript was
drafted by an AI assistant from these frozen artifacts under the author's direction, and every
quantitative and design claim was checked against the committed sources; this tooling is disclosed
rather than hidden, consistent with the paper's subject. The pre-registration's limitations
(training-data contamination, no syscall sandbox against mutant-environment gaming, a two-run
flake check that a one-third-flaky test still clears roughly four times in nine, a single fixed
Tester model, one subject's stdin code path, and one subject's pinned-module divergence from its
development branch) are carried into a dedicated Threats to Validity section rather than asserted
away here.

---

## RECEIPTS — claim-to-source traceability (for audit; not part of the paper)

- 3.1 loop mechanics, dry/max rounds, mechanical verdict, "no model judges output"
  -> PROTOCOL.md sec 1, sec 2.
- 3.1 self-preference scoped, harness-channel forward ref -> RESULTS.md "Instrument-repair
  narrative" item 4; PROTOCOL.md v9 (this is the B3 fix: no longer absolutist).
- 3.1 "not novel" MuTAP/AdverTest -> PROTOCOL.md sec 1 claim boundary; RELATED-WORK.md.
- 3.2 arms, fixed Tester, cross critic gpt-5.6-terra, tier-match, real IDs
  -> PROTOCOL.md sec 2, v8 amendment.
- 3.2 tester-draw confound + variance numbers (69/168/50/62/65) -> RESULTS.md Limitations
  ("single-run cells are noisy"). (S1 fix: disclosed at arm definition.)
- 3.3 subject table both denominators: mutants 255/80/71/69/187; existing-suite kills 0/58/46/0/0;
  survivors 255/22/25/69/187 -> PROTOCOL.md sec 3 smoke table + v6/v7 validate_scopes table;
  RESULTS.md full cell table (survivors col). (S6 fix.)
- 3.3 provenance (3 author repos, 2 OSS), strip_tests kept/stripped -> PROTOCOL.md sec 3. (S5 fix.)
- 3.3 degenerate attrition 0/255 -> PROTOCOL.md sec 3.1.
- 3.3 no equivalent-mutant detection, kill rates are lower bounds -> (Missing-piece 1 fix;
  equivalence not handled in PROTOCOL, stated honestly).
- 3.4 mutmut rule-based single-change, scope corrected only via logged amendments
  -> PROTOCOL.md sec 3.2, sec 3.4; v4/v6 scope amendments. (S4 + missing-piece 6 fix.)
- 3.5 doubled exact binomial tail min-tail doubling, n=0 -> PROTOCOL.md sec 4. (S9 fix.)
- 3.5 clustering/independence caveat, idna 64/105 -> RESULTS.md H1 table. (S2 fix.)
- 3.5 no a priori power analysis, "not detectable at this power" -> RESULTS.md H2 verdict +
  Limitations "ceiling effects cap H2's power." (S3 fix.)
- 3.6 assert byte-identical-to-HEAD, criteria pre-fixed, "receipts" defined, subgroup language
  mirrors sec 5, rerun/attempt-budget caveat, 14-of-15 + missing cell + degenerate pooled views
  -> PROTOCOL.md sec 3 intro, sec 5, sec 6, sec 7; v11 stopping rule; RESULTS.md Counted cells +
  H1 composition note. (S7, S8, S11, Q1 fixes.)
- 3.7 exact metering, UnpricedModel fail-closed, cost-per-kill scoped w/ RoP $/CVE boundary
  -> PROTOCOL.md sec 9, sec 4; RELATED-WORK.md Claim 2. (S10 fix.)
- 3.8 three-tier amendment taxonomy (free / post-paid-reclassification / final-review), "more
  spent on invalidated than counted," ten+one amendments -> PROTOCOL.md v2-v11; RESULTS.md
  "Instrument-repair narrative" + Total spend ($5.68 invalid vs $4.23 counted). (B1, B2, B4 fixes.)
- 3.9 prompt v3 + v7 hint hashed, artifacts public, repro command, AI disclosure, threats ref
  -> PROTOCOL.md v3/v7, sec 8; RESULTS.md intro (reproduce command). (Missing-pieces 2/3/4 fix.)

## CHANGELOG v2 -> v3 (keyed to Fable finding IDs)

- B1 fixed: 3.8 rewritten as honest three-tier taxonomy; removed false "caught before any paid
  data." B2 fixed: validator/canary scoped to when they existed. B3 fixed: 3.1 self-preference
  no longer absolutist, forward-refs the harness channel. B4 fixed: "ten numbered + one
  prompt-template amendment," not "eleven times."
- S1-S11 folded: tester-draw confound (3.2), clustering caveat + exact-tail precision + power
  language (3.5), scope-amendment honesty (3.4), subject provenance + both denominators + equiv-
  mutant note (3.3), rerun/attempt-budget + subgroup language + receipts definition (3.6),
  cost-per-kill boundary (3.7).
- Missing pieces added: equivalent mutants (3.3), reproducibility/artifact/AI-disclosure/threats
  (new 3.9), mutation-operator characterization (3.4). Q1 (surface missing cell) done in 3.6.
  Q2 (saga = one paragraph, Method) kept, paragraph rewritten. Q3 (real model IDs) stated in 3.2.

## REMAINING TODO (real repo facts to pull before final; NOT invented here)

1. Exact selection criteria text from experiments/SELECTION.md -> tighten 3.3's "criteria fixed
   before selection" into the actual criteria.
2. Exact prompt v3 + v7 hashes, mutmut/pytest/Python versions, OS, and model decoding params
   (temperature etc.) -> fill the specifics in 3.9 from the repo (do not guess).
3. Prior-art expansion is a Related Work task, not Method -> parked list in
   paper-related-work-todo.md (7 papers to verify + cite).
4. Pilot rule (graph-guard pre-declared pilot) -> Fable flagged omitting a pre-registered design
   element; decide whether to add one clause in 3.2/3.3 or note it in Threats.
