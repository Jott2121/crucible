# Related Work — LOCKED (v2; Jeff approved 2026-07-13; Fable-verified lockable; VERIFY-BEFORE-FINAL items = camera-ready checklist)

> Staged in scratchpad, NOT committed. No em-dashes. Every cited paper appears in either the
> frozen docs/RELATED-WORK.md (already full-text verified) or the web-verified bibliography
> (paper-related-work-verified.md, arXiv ids source-confirmed). arXiv ids shown inline in [brackets]
> for traceability; a proper bib will replace them at assembly. RECEIPTS + a reconciliation note at
> the bottom. Nothing here is cited from memory.

---

## 6. Related Work

### 6.1 LLM-based test generation

A large recent literature uses large language models to generate unit tests directly. TestPilot
[arXiv:2302.06527, TSE 2024] generates JavaScript tests from signatures and documentation usage
examples with no additional training; ChatTester [arXiv:2305.04207] and ChatUniTest
[arXiv:2305.04764] add generate-then-repair loops that fix compilation and assertion errors in
model-written tests. For Python specifically, CoverUp [arXiv:2403.16218, FSE 2025] interleaves
coverage analysis with iterative model dialogs to target uncovered lines, and CodaMosa
[ICSE 2023], building on the search-based generator Pynguin (Lukasczyk and Fraser), queries a model
to re-seed search when coverage plateaus. HITS [arXiv:2408.11324, ASE 2024] decomposes complex
methods into slices for higher coverage. At industrial scale, TestGen-LLM [arXiv:2402.09171,
FSE 2024] extends existing test classes only when a generated test verifiably builds, passes
reliably, and increases coverage, using that filter to eliminate hallucinated tests. These systems
establish that models can write useful tests and that a filter is needed to trust them, but they
gate on coverage or on compile-and-pass repair, not on fault detection. Our work differs in the
gate: it scores generated tests by the mutants they kill, a stronger signal than coverage, and it
is the adversarial survivor-feedback loop, not one-shot generation, that our H1 evaluates. This
study does not include a non-LLM search-based baseline such as Pynguin or EvoSuite; the comparison
of interest here is one-shot versus adversarial-loop LLM generation, not LLM versus search-based
generation.

### 6.2 Mutation testing with language models

Mutation testing supplies the mechanical oracle for this work, and several systems combine it with
language models. MuTAP [arXiv:2308.16557; IST 2024] re-prompts a single model with its surviving
mutants (produced by the rule-based tool MutPy) to generate tests that kill them, halting when no
survivors remain; it is single-agent, benchmark-scale, and reports mutation score with no dollar
cost. Meta ACH [arXiv:2501.12862, FSE 2025] uses three agents (fault generation, equivalence
detection, and test generation) with a single backbone model to produce few, concern-specific
mutants and hardening tests at industrial scale, under an assured generate-and-test filter.
LLMorpheus [arXiv:2404.09952] instead generates the mutants themselves with a model, producing
diverse bug-like mutants beyond a standard operator set, and a recent empirical study
[arXiv:2406.09843, TOSEM] compares such model-generated mutants against real bugs at scale. Our
mutants are rule-based (mutmut), as in MuTAP, rather than model-generated as in LLMorpheus and
AdverTest; this keeps the injected defect independent of any model under test.

### 6.3 Adversarial and dual-agent test-versus-mutant loops

The closest neighbor is AdverTest [arXiv:2602.08146], which runs a genuine dual-agent adversarial
loop: a test agent and a mutant agent iteratively attack each other under an execution-based
mutation-kill oracle, with measured fault-detection gains over prior baselines. Crucially, both of
AdverTest's agents share a single backbone model per configuration, and no cross-lineage
configuration is measured. Our loop replicates this adversarial-under-a-mechanical-oracle pattern,
and we claim it as a replication, not an invention (Section 5.1). What AdverTest and the
survivor-feedback lineage of MuTAP do not do, and what our H2 measures, is vary the lineage of the
critic against a same-lineage control under the mechanical oracle.

### 6.4 Cross-model diversity, self-preference, and evaluation bias

The premise that a mechanical oracle is worth its cost rests on a known failure of model-graded
evaluation: large language model evaluators can recognize and favor their own generations
[Panickssery, Bowman, and Feng, arXiv:2404.13076, NeurIPS 2024], a self-preference bias a
model-graded verdict cannot escape. Heterogeneous-model methods such as multi-agent debate
[Du et al., arXiv:2305.14325,
ICML 2024] motivate the intuition that mixing model lineages helps, but the direction is genuinely
open: Self-MoA reports same-model repeated sampling beating heterogeneous mixtures on reasoning
benchmarks, and Refute-or-Promote [arXiv:2604.19049] argues a cross-model critic catches correlated
blind spots but does so in defect discovery, without a controlled same-lineage ablation and without
a purely mechanical oracle. Most directly relevant to our Discussion, recent work argues that models
increasingly share the same errors, which undermines the reliability of using one model to oversee
another [Great Models Think Alike and this Undermines AI Oversight, arXiv:2502.04313]. Our
instrument autopsy (Section 5) is a concrete, receipted instance of a related but distinct hazard:
even with model judgment removed from the verdict entirely, an asymmetry in the harness that feeds
the two models can manufacture a large false cross-model difference.

### 6.5 Cost accounting and pre-registration

Where cost is reported in this literature, it is normalized to an input unit rather than an outcome.
AdverTest reports an average dollar cost per method-generation run (for example $0.270 on
Defects4J), and TestForge [arXiv:2503.14713] reports dollars per file and per iteration, but neither
divides cost by mutants killed or faults detected. The nearest per-outcome figure is in an adjacent
domain, defect discovery, where a cross-model critic system reports roughly $62 per discovered
vulnerability. To our knowledge our cost-per-kill is the first per-outcome cost figure reported in
LLM test generation. Separately, pre-registered and registered-report protocols have precedent in
software engineering [arXiv:2302.03649] and have begun to wrap LLM-for-software-engineering studies
[arXiv:2606.10702], though they remain uncommon in this literature; we adopt pre-registration as a
matter of rigor and claim no priority for it.

### 6.6 Positioning

To our knowledge, no prior work measures the effect of critic-generator lineage diversity on
test-suite fault detection under a mechanical mutation-kill oracle, nor reports LLM test-generation
cost normalized per killed mutant. We do not claim to be first to run an adversarial
test-versus-mutant loop under a mechanical oracle (AdverTest does this), first to feed survivor
mutants into model prompts (MuTAP does this), or first to pre-register a software-engineering
protocol. We claim a controlled cross-lineage versus same-lineage critic measurement under a
mechanical oracle, a per-outcome cost figure new to this literature, a replication of the
MuTAP-to-AdverTest direction in an agentic repo-level Python setting with disclosed costs, and,
as the durable contribution, a fully receipted autopsy of a lineage-correlated instrument artifact.

---

## RECEIPTS — every cited paper traces to a verified source (not memory)

Frozen ledger (docs/RELATED-WORK.md, already full-text verified): MuTAP [2308.16557], AdverTest
[2602.08146], Meta ACH [2501.12862], Refute-or-Promote [2604.19049], TestForge [2503.14713],
Self-MoA, pre-registration precedents [2302.03649, 2606.10702], and the claim-boundary paragraph
(6.6 mirrors it).
Web-verified bibliography (paper-related-work-verified.md, arXiv ids source-confirmed): TestPilot
[2302.06527], ChatTester [2305.04207], ChatUniTest [2305.04764], CoverUp [2403.16218], CodaMosa
(ICSE 2023) + Pynguin, HITS [2408.11324], TestGen-LLM [2402.09171], Panickssery [2404.13076], Du
[2305.14325], LLMorpheus [2404.09952], Comprehensive Study [2406.09843], Great Models Think Alike
[2502.04313].

## RECONCILIATION NOTE (caught by reading the frozen ledger before drafting)

- Meta ACH (frozen ledger) IS "Mutation-Guided LLM-based Test Generation at Meta," Foster et al.,
  arXiv 2501.12862, FSE 2025. The web agent surfaced this as a "new" Foster paper; it is NOT new,
  it is already cited. Cited once, as Meta ACH. No double-cite.
- TestGen-LLM (Alshahwan et al., arXiv 2402.09171, FSE 2024) is a DIFFERENT, earlier Meta paper
  (coverage-filter), added new to 6.1.
- Dakhel et al. 2024 (IST) that the web agent surfaced is the journal version of MuTAP, already
  covered; not double-cited.

## CHANGELOG v1 -> v2 (keyed to Fable finding IDs)

- SHOULD-FIX-1: 6.4 self-preference softened to the title's assertion ("recognize and favor their
  own generations"); the un-sourced "scales with self-recognition ability" removed and moved to
  VERIFY-BEFORE-FINAL.
- SHOULD-FIX-2: 6.1 "measure and gate on coverage" -> "gate on coverage or on compile-and-pass
  repair, not on fault detection" (ChatTester/ChatUniTest gate on repair, not coverage).
- SHOULD-FIX-4: 6.1 adds one sentence naming Pynguin/EvoSuite as the non-LLM SBST baseline this
  study deliberately does not use (preempts "why no SBST baseline").
- RULING-1: folded old 6.5 (cost) + 6.6 (pre-registration) into one 6.5; Positioning is now 6.6.
- RULING-2: Assured LLMSE [2402.04380] omitted for the workshop version (TestGen-LLM + Meta ACH
  already cover the Meta line; avoid over-citing one lab).
- RULING-3: kept self-preference as the 6.4 spine.
- Also: fixed the STALE note in paper-related-work-verified.md (item 1c wrongly said 2501.12862 is
  NOT Meta ACH; it IS -- corrected in that file).

## VERIFY-BEFORE-FINAL (do not skip; grep/lookup at assembly)

- Panickssery et al.: the fuller finding (self-preference "scales with self-recognition ability") is
  the paper's real result but is NOT in the verified sources on hand; confirm from the paper before
  restoring it, or leave 6.4 at the title-level assertion (currently safe).
- Pynguin exact bibliographic record (title/venue/year) -- COULD NOT VERIFY; cited only as the tool
  CodaMosa builds on and now as an SBST baseline name. Confirm before camera-ready.
- EvoSuite: newly named in 6.1; confirm the standard citation (Fraser and Arcuri) at assembly.
- "Great Models Think Alike" [2502.04313]: confirm exact author list at assembly (non-load-bearing
  supporting cite).
- Bib-only finding paraphrases (LLMorpheus "diverse bug-like mutants," Du "mixing lineages helps,"
  Comprehensive Study "851 real Java bugs") -- confirm alongside their ids at assembly.

## OPEN QUESTIONS

None outstanding; Fable's three rulings applied above. Related Work is Fable-ruled lockable-as-design;
the VERIFY-BEFORE-FINAL items are camera-ready checklist, not workshop-submission blockers.
