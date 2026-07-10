# Related Work — Claim Ledger

## Purpose and method

This document is the evidence base for the four novelty/scope claims made in the pre-registered
experiment design (design doc section 1b). It was produced *before* PROTOCOL.md froze, as the
blocking related-work sweep that section 1b requires: each claim below either gets confirmed as an
open gap, or the experiment re-scopes. Every factual sentence about a system traces to a full-text
verification pass; every claim verdict traces to a recorded adversarial search.

Two passes produced the evidence. First, full-text verification: the three closest prior systems
(MuTAP, AdverTest, Meta ACH) were read from their primary sources (arXiv PDF/HTML, journal DOI, or
ACM DOI) and checked question-by-question against the four claims, quoting section numbers and
exact language rather than summarizing from memory. Second, an adversarial novelty sweep: for each
claim, multiple independent phrasings were searched across semantic paper search, citation-graph
expansion, and direct web search, with every query, hit, and dead end logged, followed by full-text
reads of the strongest near-miss papers to confirm they do not already satisfy the claim. Where a
source text did not address a question, that is recorded as "no evidence found," never filled in
from general knowledge.

## Systems

### MuTAP

MuTAP (Dakhel, Nikanjam, Khomh, Desmarais, Washizaki) is verified from the arXiv PDF
(arxiv.org/pdf/2308.16557) and its journal version in Information and Software Technology
(DOI 10.1016/j.infsof.2024.107468). Mutants are produced by a traditional rule-based tool, MutPy
v2.0, not by an LLM: "MutPy injects one operator at a time to generate the mutants" (Table 1 lists
operators AOR, ROR, LCR, etc.). Surviving mutants are fed back by prompt augmentation: MuTAP
"re-prompts its LLMC to generate new test cases for the PUTs that have surviving mutants by
augmenting the initial prompt with both initial test cases and the surviving mutants," halting when
all mutants are killed or no unused survivors remain. Models: a single LLM component (LLMC) per
configuration, either OpenAI Code-davinci-002 (temperature 0.8) or Meta Llama-2-chat — one
single-backbone lineage per run, with no separate critic/reviewer model; the only "adversary" is the
deterministic MutPy tool. Benchmark/scale: HumanEval (164 programs under test, 1260 mutants) and
Refactory (1710 buggy student submissions). Headline metric is Mutation Score (ratio of killed
mutants); MuTAP reaches MS 93.57% and detects up to 468 (28%) more buggy human code than baselines.
No dollar or per-outcome cost figures are reported anywhere — only generation-length token caps
(250 tokens for test cases, 20 for syntax fixing). Guardrail: an "Intended Behavior Repair" step
runs the test against the original correct PUT and replaces wrong asserted values, so assertions are
corrected against ground truth before scoring; kill verdicts are execution-based. Code: the paper
states a replication package is publicly available (anonymized GitHub link in the arXiv text).
(arxiv.org/pdf/2308.16557; DOI 10.1016/j.infsof.2024.107468)

### AdverTest

AdverTest ("Test vs Mutant: Adversarial LLM Agents for Robust Unit Test Generation," Chang, Fang,
Chen, Shi, Shen, Gu, SJTU/CMU) is verified from arXiv HTML v2 (arxiv.org/html/2602.08146v2, CC BY
4.0). It runs a genuine dual-agent adversarial loop: a test-generation agent (T) and a mutant-
generation agent (M), where "M persistently creates new mutants 'hacking' the blind spots of T's
current test suite, while T iteratively refines its test cases to 'kill' the challenging mutants
produced by M." M is a prompt-driven LLM mutant generator (single-line-change constraint, few-shot
examples from QuixBugs), not a rule-based tool — this is the closest neighbor to a cross-role
adversarial design. Models/lineage: both agents run on one shared backbone per configuration —
"DeepSeek-v3.2, GPT-OSS-120B for both agents" (section 4.4) — varied across whole-system runs but
never mixed within a run; no cross-lineage configuration is measured. Loop structure: fixed N
rounds (Algorithm 2), T augments first each round, then M augments mutants, with a final T pass so
"T always has the final move"; newly added tests are deferred to the next cycle rather than
immediately re-evaluated, to avoid token blow-up. Verdict is execution-based: a mutant counts as
killed only if Δ = Fail(T,m) \ Fail(T,P) is non-empty, i.e., a test fails on the mutant but not on
the unmodified program P (Algorithm 1); invalid (non-compiling/timeout) mutants are discarded, but
there is no explicit equivalent-mutant detector. Metrics: Fault Detection Rate (primary), line/branch
coverage, and dollar cost — "we track token usage throughout the entire generation process of each
method and report the average cost per method." Table 1 reports average dollar cost per
method-generation run, e.g. $0.270 on Defects4J/DeepSeek, $0.245 on GrowingBugs, $0.553 on GPT-OSS,
versus HITS $0.411 and ChatUnitTest $0.113 — a per-run average, not divided by kills or faults.
Scale: Defects4J (200 sampled defects, 17 projects, v2.1.0) plus GrowingBugs, totaling 20 projects,
247 bugs, 727 methods under test, Java 8/JUnit 4/Mockito 4.11. Headline result: FDR 66.63% on
Defects4J with DeepSeek V3.2 (+8.6% relative over HITS, +63.3% over EvoSuite). Availability: "All
code and data used in this study are publicly available at github.com/jmueducn/AdverTest."
(arxiv.org/html/2602.08146v2; arxiv.org/abs/2602.08146; github.com/jmueducn/AdverTest)

### Meta ACH

Meta ACH ("Mutation-Guided LLM-based Test Generation at Meta," Foster, Harman, Ritchey et al.) is
verified from arXiv HTML (arxiv.org/html/2501.12862v1), the preprint of an FSE Companion '25
industry paper (DOI 10.1145/3696630.3728544). Design: three LLM agents — "Make a fault" (writes a
concern-targeted mutant, e.g. "a typical bug that introduces a privacy violation similar to
{diff}"), "Equivalence detector," and "Make a test to catch fault" — deliberately generating few,
concern-specific mutants rather than exhaustive traditional mutation. Models/lineage: single —
"The single language model Llama 3.1 70B was used in all the agents reported on," with the authors
explicitly stating they have "not yet felt the need... to exploit language model ensembles." Loop:
Assured LLMSE — a proposed test must verifiably compile, pass on the original class, and fail on the
mutant (kill) before it can surface; the Equivalence Detector separately filters equivalent mutants
using weak mutation semantics. Detector precision/recall (Table 6): 0.79P/0.47R (unsure counted as
equivalent), 0.97P/0.44R (unsure counted as non-equivalent), and 0.95P/0.96R combined with a
rule-based pre-processor that strips comments and removes syntactically identical mutants. Scale:
10,795 Android Kotlin classes across 7 software platforms at Meta (Oct 28-Dec 31, 2024), generating
9,095 mutants and 571 privacy-hardening test cases. Engineer acceptance: 73% of ACH's tests accepted
in Messenger/WhatsApp test-a-thons, 36% judged privacy-relevant. Cost: none reported — no "cost,"
"$," or "token" economics appear as metrics, only qualitative "computational resource" language.
Guardrails: the strongest of the three systems — compile+pass-on-original+kill-mutant verification,
an independent Equivalence Detector, separate agents for mutant vs. test generation, and a final
human-in-the-loop gate via standard CI code review. Availability: internal/proprietary, deployed
inside Meta with no public code release; the paper is the only public artifact.
(arxiv.org/html/2501.12862v1; arxiv.org/abs/2501.12862; DOI 10.1145/3696630.3728544)

## Claim ledger

### Claim 1 — Cross-lineage critic under a mechanical oracle

None of the three verified systems measures a cross-lineage critic effect. MuTAP's only adversary is
a deterministic tool (MutPy), not a model, and its single LLMC both generates and refines tests.
AdverTest runs its test agent (T) and mutant agent (M) on one shared backbone per configuration
("DeepSeek-v3.2, GPT-OSS-120B for both agents") and never crosses lineages within a run. Meta ACH
uses one model, Llama 3.1 70B, "in all the agents," explicitly forgoing ensembles.

An adversarial novelty sweep (roughly seven distinct phrasings — cross-model, cross-lineage,
heterogeneous, model-diversity, cross-family critic, crossed with test generation / test hardening /
mutation — across semantic paper search, citation-graph expansion, and web search) surfaced two
near-misses, both full-text verified and both falling short of the claim:

- **Refute-or-Promote (arXiv 2604.19049)** uses a Cross-Model Critic (CMC) and argues cross-family
  review "can catch correlated blind spots that same-family review misses." It falls short on three
  counts: (a) domain is vulnerability/defect discovery, not test generation; (b) the paper states
  explicitly "no ablation studies isolating individual mechanisms" — the cross-lineage benefit is
  asserted from n=2 anecdotal "unanimity-as-warning" cases, not measured against a same-lineage
  control; (c) the verdict blends LLM judgment with a partially mechanical PoC gate, not a pure
  mechanical (mutation-kill/execution) oracle.
- **AdverTest (arXiv 2602.08146)** is the closest in-domain system — adversarial LLM test-gen vs.
  LLM mutant-gen under a genuinely mechanical mutation-kill oracle — but both agents share a single
  backbone per configuration; no cross-lineage vs. same-lineage comparison is run.

A counter-current was also found and is worth citing: Self-MoA reports same-model repeated sampling
beating heterogeneous mixture-of-agents by 6.6% on reasoning benchmarks, so the direction of a
cross-lineage effect is genuinely open, not assumed in our favor.

**CONFIRMED OPEN.**

### Claim 2 — Cost-per-outcome economics

No system among the three, and none of the near-misses found in the sweep, normalizes cost to an
outcome (per killed mutant, per detected fault, or per quality-unit). MuTAP reports only token
generation caps (250/20), no dollars. Meta ACH reports no dollar or token figures at all, only
qualitative "computational resource" language. AdverTest reports the sharpest adjacent number:
average dollar cost per method-generation run — $0.270 on Defects4J/DeepSeek, $0.245 on GrowingBugs,
$0.553 on GPT-OSS — but this is cost per method-run, not divided by kills or faults. TestForge
(arXiv 2503.14713) reports real USD figures — $0.63 per file, $0.04 per iteration — "to ensure
economically viable" generation, alongside mutation score as a separate metric, but likewise never
divides cost by kills or faults; its economic unit is $/file. A direct adversarial web search for
the exact phrasing `"cost per killed mutant"` / `"dollars per fault"` in LLM test generation
returned zero results — a strong negative signal. (Other adjacent cost figures found but further
from the claim: mu-BERT reports cost-effectiveness in mutants-analyzed compute, not dollars;
Refute-or-Promote reports ~$62/CVE, but in defect discovery, not test generation.)

Our claim is scoped precisely to cost *per outcome* (dollars per killed mutant / per detected
fault), citing AdverTest ($0.270/method-run) and TestForge ($0.63/file) as the two nearest
neighbors that report real dollar costs in this literature without ever computing this ratio.

**CONFIRMED OPEN.**

### Claim 3 — Open governance-first implementation

From verified facts only, the boundary is: Meta ACH is internal-only, with no public code release —
"the paper is the only public artifact." AdverTest's code is public
(github.com/jmueducn/AdverTest) but is a research artifact: it has no disclosed guardrail layer
beyond the execution-based kill check and repair loop, and no receipt/audit layer — its stated
guardrails are agent-role separation, the pass-on-original kill constraint, and a repair loop
requiring compilable/valid tests, with no explicit anti-gaming or equivalent-mutant handling. MuTAP
is public (a replication package is stated to be available) but is single-agent: one LLM component
performs both generation and refinement, with no separate critic role and no governance layer beyond
MutPy-owned mutants and the Intended Behavior Repair step. None of the three combines public code,
a cross-agent guardrail/anti-gaming layer, and a receipt/audit trail in one open implementation.

### Claim 4 — H1 framing (replication, not priority)

The verified MuTAP-to-AdverTest lineage establishes the direction this project replicates:
survivor-feedback into LLM prompts (MuTAP, benchmark-scale, single-agent, Codex/Llama-2) evolving
into a dual-agent adversarial test-vs-mutant loop under a mechanical oracle (AdverTest, Java,
Defects4J/GrowingBugs scale, cost reported per method-run). This project's H1 is a replication of
that direction in a new setting — agentic, repo-level, Python, with disclosed costs — not a claim of
priority. AdverTest already establishes the adversarial-loop-under-mechanical-oracle pattern with
measured fault-detection gains (+8.6% relative FDR over HITS); this project is not the first to run
that pattern, only the first (per the Claim 1 sweep) to run it with a controlled cross-lineage vs.
same-lineage critic comparison in a repo-level Python agentic setting with dollar costs disclosed
per outcome.

### Claim 5 — Pre-registration

Pre-registered / registered-report protocols exist in software engineering generally — Registered
Reports in SE (arXiv 2302.03649) and an OSF-based RR template for SE (arXiv 2602.09292) — and a
small number specifically wrap LLM-for-SE studies, including Watts and Debts (arXiv 2606.10702).
Reproducibility-crisis surveys covering roughly 640 LLM-for-SE papers document weak
pre-registration/reproducibility norms across the field. So pre-registration is not novel in
software engineering, and is not unprecedented even for LLM-for-SE work, but remains uncommon in
this literature.

**Pre-registration is framed as rigor, not novelty** — citing arXiv 2302.03649 and arXiv 2606.10702
as evidence it has precedent, not as evidence this project originated it.

## The claim boundary paragraph

To our knowledge, no prior work measures the effect of critic-generator lineage diversity
(cross-lineage vs. same-lineage) on test-suite fault detection under a mechanical mutation-kill
oracle, nor reports LLM test-generation cost normalized per killed mutant or per detected fault; the
closest systems either share a single model backbone across adversarial roles (AdverTest, arXiv
2602.08146), assert cross-family benefit without a controlled ablation in a different domain
(Refute-or-Promote, arXiv 2604.19049, defect discovery, "no ablation studies"), or report cost per
file or per method-run rather than per outcome (TestForge, arXiv 2503.14713; AdverTest). We do not
claim to be first to run an adversarial test-vs-mutant loop under a mechanical oracle (AdverTest
already does this), first to feed survivor mutants into LLM prompts (MuTAP already does this), or
first to pre-register an empirical software-engineering protocol (established precedent exists,
arXiv 2302.03649, arXiv 2606.10702). We claim only: the first controlled measurement of cross-lineage
vs. same-lineage critic effect under a mechanical oracle, the first cost accounting normalized per
killed mutant / per detected fault in this literature, and a replication of the MuTAP-to-AdverTest
adversarial-loop direction in a new agentic, repo-level, Python setting with disclosed costs.
