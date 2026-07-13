# Discussion — LOCKED (v2; Jeff read + approved 2026-07-12; Fable-verified lockable, receipts grep-audited clean)

> Staged in scratchpad, NOT committed. No em-dashes. CHANGELOG + hand-verified RECEIPTS at the
> bottom (v1 contained one fabricated citation; every receipt in this version re-checked against
> the frozen files). Limitations/Threats and Related Work are separate sections.

---

## 5. Discussion

### 5.1 What H1 establishes, and what it does not

H1 is a replication, and we are careful to claim it as one. The result that the adversarial loop
strictly dominates one-shot generation, killing 105 discordant mutants to zero across four
subjects, confirms in a new setting (agentic, repo-level, Python, with a mechanical mutation-kill
oracle) an effect already established by MuTAP and AdverTest. Replication in a new setting is a
contribution, but it is not a discovery, and the strength of the pooled p-value does not change
that. The value of this particular replication is narrower and more concrete: it comes with
disclosed per-outcome costs, and it survived an instrument-correction process that, as it happened,
made the effect larger rather than smaller (Section 4.2), because the defect described below had
been suppressing the loop's own rounds. An effect that grows when you fix the instrument working
against it is a more trustworthy effect than one that shrinks.

### 5.2 The instrument autopsy

The paper's central contribution is not H1 and not the loop. It is a fully receipted account of how
this study's own measurement instrument manufactured a large, false result, how that result was
caught, and what it cost to catch it.

**What appeared.** Before the correction, H2 read as strongly supported: a pooled exact McNemar of
p = 9.5e-66, with 217 discordant pairs favoring the cross-lineage critic and none against. On its
face this was an overwhelming demonstration that a different-lineage critic outperforms a
same-lineage one. It was almost entirely false.

**The defect.** The provider wrapper for the same-lineage model set a fixed output ceiling
(max_tokens = 16000) on every one of its calls, and nowhere in the calling code was a reply's
output-token count ever compared against that ceiling, nor was the truncation signal the API
returns ever inspected. A reply that hit the ceiling came back as ordinary, well-formed-looking
text that happened to be cut off mid-file. At the call site it was indistinguishable from a
complete reply. It was handed to test validation, which rejected it for an unrelated-sounding
reason (a truncated code block reads as "expected exactly one fenced python block, found 0"; a
syntactically broken test file reads as "invalid: fails on pristine code"), and the round was
recorded as rejected under that misleading note, crediting zero kills, with no trace anywhere in
the receipts that the reply had in fact been silently cut off, billed, and discarded. Across the
counted cells, eight rounds were recorded rejected, and seven of them had billed exactly 16,000
output tokens.

**Why this faked a cross-lineage effect rather than adding noise.** This is the crux, and it is
what makes the defect a confound rather than random error. The truncation was not evenly
distributed across the two critic arms. The same-lineage critic is the verbose model: its replies,
which walk through each survivor's diff and reasoning, routinely approached or exceeded the 16,000
token ceiling. The cross-lineage critic is terse and never hit any ceiling in any counted cell (its
accepted-round output ranged from a few hundred to a few thousand tokens). So the truncation
failure was systematically correlated with exactly the variable H2 was measuring. It did not blur
the comparison; it manufactured one. The same-lineage arm was the only one mechanically capable of
losing whole rounds to silent truncation, which biased the measurement toward making the
same-lineage critic look worse than its real output, for a reason having nothing to do with test
quality or lineage. When the defect was corrected and the four affected cells rerun, the apparent
effect collapsed: the pooled p of 9.5e-66 became p = 0.0625, not significant. The clearest single
illustration is packaging, whose 32-to-0 discordant gap favoring the cross-lineage critic became
0-to-0 after its same-lineage critic's rounds were rerun without truncation. Because that rests on
a single rerun of a cell class with real run-to-run variance, the well-supported reading is that
the ceiling had been deleting the verbose model's rounds, rather than a mechanical decomposition
that fully excludes ordinary tester-round variance.

**How it was caught.** Not by a runtime gate. This study caught three earlier silent-corruption
mechanisms mechanically, each before any number reached a results file: a sandbox crash that would
have laundered into a false all-survived zero, and a scoping bug that would have silently prevented
freshly generated tests from ever being collected, among them. The truncation defect slipped all of
those gates, because it produced no crash and no error, only a plausible rejection note. It was
caught by a final adversarial review that read the completed analysis, after every counted cell had
already run, and asked why exactly these rounds were failing. That a defect this consequential
survived every mechanical check and was caught only by an independent skeptical read is itself part
of the finding.

**The fail-loud repair.** The fix makes the instrument halt loudly rather than emit a plausible
wrong number. The output ceiling is now a single mechanical value read by both the request and a
new check: every reply's output-token count is compared against it, and a reply at the ceiling
raises a truncation error that is never retried (retrying a capped call would bill again and likely
truncate again). The round is recorded honestly as "truncated: output hit max_tokens cap," its real
billed cost is metered, zero kills are credited, and the raw truncated reply is archived as
preserved evidence. A truncation at the first round of a cell fails that cell loudly as missing
data rather than being silently recovered. The principle is fail-closed: when the instrument cannot
measure, it must say so, not hand back a confident wrong number.

**A residual asymmetry we disclose rather than paper over.** The truncation check exists only where
a mechanical ceiling is declared, which is the same-provider wrapper. The cross-lineage provider
sends no such ceiling and is therefore never truncation-checked. If that provider ever truncated a
reply against a server-side limit, this instrumentation would launder it exactly the way the
original defect did. We have no evidence any such truncation occurred (every accepted cross-lineage
round is far from any plausible ceiling), but the detection asymmetry is structural and we name it,
because the entire point of this section is that undisclosed asymmetries are how false results get
made.

### 5.3 The general lesson: cross-model comparisons can inherit the asymmetries of their harness

The mechanical oracle at the core of this design was adopted specifically to close the
self-preference channel that undermines LLM-as-judge evaluation, where a model scoring model output
has no ground truth. At the verdict level it did exactly that: no model ever judged another model's
output, and the kill verdict is a seeded defect and a failing test. The autopsy's payload is that a
different bias, one level out from the verdict, survived the very mechanism meant to make
model-versus-model comparison safe. Closing the judgment channel did not make the comparison
neutral, because the apparatus that fed the two models was not itself symmetric.

The lesson generalizes beyond the specific defect. A comparison is only as neutral as the apparatus
that runs it, and an apparatus that treats the two models differently in any dimension correlated
with the outcome can produce a difference that looks like a model difference and is not. Here the
correlated dimension was output verbosity interacting with a truncation ceiling; in another study
it could be a timeout, a token budget, a rate limit, a retry policy, or a parser that tolerates one
model's formatting quirks and not the other's. The defect is dangerous precisely because it is
invisible in the result: the manufactured p-value was clean, well-formatted, and enormous. Nothing
about the number announced that it was measuring the harness rather than the models.

Two practices follow, and this study argues for both by having needed both. First, pre-registration
of the hypotheses and success criteria, so that a result cannot be quietly reinterpreted after the
fact and so that the difference between the pre-declared analysis and the corrected one is itself a
visible, dated record. Second, and less commonly practiced, fail-closed instrumentation: a
measurement pipeline should be built so that when a component cannot do its job, it halts loudly
instead of emitting a plausible substitute. Most of the silent corruptions in this study were
caught because the instrument was progressively rebuilt to fail loud; the one that reached the
counted data was the one place the instrument could still fail silently.

### 5.4 Why the null and the autopsy are the contribution

It would have been easy, and wrong, to publish the p = 9.5e-66 result. It was pre-registered, it
was in the right direction, and it was produced by real runs against real subjects. A study that
stopped at its first significant result would have reported a large cross-lineage effect that the
corrected data do not support. What prevented that was not a better model or a cleverer method; it
was an evidence discipline that treated the instrument as a suspect and subjected the completed
analysis to an adversarial read before publication. The replication (H1) confirms known work. The
null (H2), honestly reported as underpowered rather than as evidence of no effect, is the
pre-declared second finding. But the durable contribution is the autopsy: a worked, receipted
example of a lineage-correlated instrument artifact manufacturing an extraordinary false result,
caught before publication, with the fail-loud repair that prevents its recurrence. Cross-model
evaluation is now routine in software-engineering research and practice; this study documents, with
receipts, one concrete way such evaluations silently go wrong, and what it takes to catch it.

A properly powered test of the cross-lineage question would need three things this study lacked:
subjects with survivor headroom below the 98.6 to 100 percent kill ceiling that left three of four
scorable subjects with no discordant pairs, repeated cells per subject to separate signal from the
substantial run-to-run tester variance, and a single frozen round-0 survivor set shared by both
critic arms, which would remove the tester-draw confound noted where the arms are defined (Section
3.2). The limitations of the study, including its small subject count, its single language, its one
missing cell, the ceiling effects, and the residual detection asymmetry named above, are treated in
full in the Threats to Validity section.

---

## CHANGELOG v1 -> v2 (keyed to Fable finding IDs)

- BLOCKING-1 fixed: "four earlier silent-corruption mechanisms" corrected to "three" (frozen
  RESULTS.md Instrument-repair narrative); the FABRICATED PROTOCOL v9 quote in the v1 RECEIPTS
  block is removed; "caught mechanically" now correctly applies only to the three earlier ones, not
  the truncation defect (which was caught by the final review).
- BLOCKING-2 fixed: 5.2 packaging collapse now attributed at the pooled level, with packaging as
  illustrative carrying the same single-rerun / tester-variance caveat as Results 4.4. No more bare
  "once no longer truncated" causation. Discussion and Results now consistent.
- SHOULD-FIX-3 fixed: 5.4 "an effect that does not exist" -> "that the corrected data do not
  support" (magnitude, not existence; consistent with the underpowered-null framing).
- SHOULD-FIX-4 fixed: new opening to 5.3 bridges to LLM-as-judge / self-preference: the mechanical
  oracle closed the judgment channel but a harness-level bias survived the fix meant to make
  cross-model comparison safe. (Citations parked to Related Work.)
- SHOULD-FIX-5 fixed: 5.4 now states what a properly powered follow-up requires (headroom below
  ceiling, repeated cells, shared frozen round-0 set to kill the tester-draw confound).
- SHOULD-FIX-6 fixed: 5.3 heading "inherit" -> "can inherit," matching the hedged body.
- SHOULD-FIX-7 fixed: "scream instead of lying" -> "halt loudly rather than emit a plausible wrong
  number." Kept "manufactured one" and "almost entirely false" (both grounded in frozen RESULTS).

## RECEIPTS — claim-to-source (HAND-VERIFIED after v1's fabricated citation; not part of the paper)

- 5.1 H1 = replication, 105-to-0, strengthened (b79/c5 -> 105/0) -> RESULTS.md H1 verdict; PROTOCOL
  sec 1 claim boundary; Method 3.2.
- 5.2 old p=9.5e-66, b=217, c=0 -> RESULTS.md load-bearing finding (first paragraph).
- 5.2 max_tokens=16000, no output-token/stop_reason check, laundered as content rejection, two
  example notes verbatim, "eight rejected, seven billed exactly 16000" -> PROTOCOL.md v9 amendment
  + its 7-row truncation table; RESULTS.md Instrument-repair narrative item 4.
- 5.2 verbosity asymmetry (same-lineage verbose approaching/exceeding 16000; cross-lineage terse,
  accepted-round output hundreds to few-thousand, never capped) -> PROTOCOL.md v9 "Mechanism of the
  asymmetry"; RESULTS.md item 4.
- 5.2 collapse pooled 9.5e-66 -> 0.0625; packaging 32->0 WITH single-rerun/tester-variance caveat
  -> RESULTS.md load-bearing finding (packaging bullet, which itself carries the caveat) + H2.
- 5.2 "three earlier silent-corruption mechanisms caught mechanically" -> RESULTS.md Instrument-
  repair narrative ("The superseded analysis documented three silent-corruption mechanisms caught
  before its numbers were computed"). [v1 cited a non-existent PROTOCOL quote; removed.]
- 5.2 truncation caught by final adversarial review after all cells ran, not a runtime gate ->
  PROTOCOL.md v9 amendment header ("found by a final adversarial review of the completed analysis,
  after all 15 counted cells had already run"); RESULTS.md item 4.
- 5.2 fail-loud fix (single output_cap read by request + check, never retried, "truncated: output
  hit max_tokens cap" note, cost metered, raw reply archived, round-0 truncation fails cell loud)
  -> PROTOCOL.md v9 "Fix" paragraphs; RESULTS.md item 4.
- 5.2 residual: cross-provider sends no ceiling, never truncation-checked, no evidence any occurred
  -> PROTOCOL.md v9 "Detection asymmetry"; RESULTS.md Limitations (detection asymmetry).
- 5.3 mechanical oracle closes verdict-level judgment channel; harness-level bias survives -> Method
  3.1 (design commitment) + this section's own finding. General claim grounded in the alt-failure
  list (author reasoning, not a cited fact).
- 5.4 easy-and-wrong-to-publish; null underpowered not no-effect; contribution = autopsy; power
  requirements (headroom / repeated cells / shared round-0 set) -> RESULTS.md Summary + Limitations
  ("subjects with headroom below the ceiling ... repeated cells per subject"); Method 3.2 (tester
  confound).

## OPEN QUESTIONS (Jeff's ruling)

None outstanding from Fable; its three rulings are applied. One standing author choice remains from
earlier: the two repo-fact TODOs (exact tool versions/prompt hashes; SELECTION.md criteria text)
are still deferred to final assembly, and the Related Work section still needs the real literature
search (7 parked papers to verify). Neither blocks locking the Discussion design.
