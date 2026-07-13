# PROTOCOL-B — Experiment B (B-minimal): frozen shared round-0, causal isolation of the critic loop

Status: **PRE-REGISTERED — written before any Experiment-B paid run, and before the
Experiment-B runner exists.** The design is frozen here first; the runner is built afterward
(approved plan, step 2) and **must enforce this freeze before any paid call**: it reuses
Experiment 1's committed-byte-identity gate
(`src/crucible/experiment.py::assert_protocol_committed`) against `experiments/protocol-b.json`
and against each frozen seed directory (§2), and Phase A must refuse to start unless that
enforcement exists and is covered by passing tests. Experiment 1's own `crucible experiment`
command mechanically refuses `protocol-b.json` (unknown modes, missing `protocol_version` key)
— by design, so no Experiment-B cell can ever run through the Experiment-1 path by accident.
In addition, this protocol commit is **pushed to the public repository
(github.com/Jott2121/crucible) before the first paid run**, so the freeze carries an
externally observable timestamp. This is disclosed honestly: a pushed commit is not an
immutable third-party registration (no OSF-grade timestamping authority); it is a public,
hash-chained record that predates the data.

Companion files: `experiments/protocol-b.json` (machine-readable config the runner loads),
`experiments/DEVIATIONS.md` (the same append-only deviation log as Experiment 1; Experiment-B
entries are prefixed **"B:"**), `experiments/PROTOCOL.md` (Experiment 1, protocol_version 11 —
the design this experiment repairs; frozen, unmodified), and
`paper/gpt-5.6-review-REJECT.txt` (the cross-lineage review that motivated this experiment —
committed together with this protocol so the motivating critique is part of the same public
record).

Version: **protocol_b_version 1**. Base: Experiment 1 protocol_version 11.

## 1. Motivation and claim under test

Experiment 1's H1 (`loop-same` vs `oneshot`) compared arms that each **independently sampled
their own round-0 tester suite**. A cross-lineage review of the resulting paper
(`paper/gpt-5.6-review-REJECT.txt`, 2026-07-13) correctly identified that this design does not
isolate the loop's causal effect: `loop-same`'s round 0 is a different draw than `oneshot`'s
round 0, so the arm difference confounds (a) the critic rounds' incremental contribution with
(b) round-0 sampling variance. That variance is large — repeated tester draws against a single
subject during Experiment 1's rerun attempts produced round-0 kill counts ranging roughly
50–168 (`experiments/DEVIATIONS.md`, attrition rerun attempts). Experiment 1's H1 result
(pooled b=105, c=0, p=4.9e-32) is therefore an observation about two independently sampled
pipelines, not a paired isolation of the loop.

**Experiment B fixes exactly that confound.** For each replicate, ONE round-0 tester suite is
generated, frozen, and shared: all three continuations start from the identical frozen state.

- **E-B1 (primary, causal within this design):** the incremental kill effect of same-lineage
  critic rounds over the frozen round 0 — Δsame = kills(loop-same) − kills(no-critic), paired
  within replicate. Because generated tests are add-only and both cells share the identical
  round-0 suite, Δsame ≥ 0 **by construction**; the pre-registered question is therefore its
  **magnitude** (including whether it is ≈ 0), never its sign. No sign-based significance claim
  will be made.
- **E-B2 (secondary, pilot):** the cross-vs-same-lineage critic difference —
  D = Δcross − Δsame, paired within replicate (can be negative). This remains an honest,
  underpowered pilot: 4 subjects × 5 replicates cannot power a lineage claim, and the
  comparison bundles model, provider, and harness differences (disclosed in §9). No binary
  supported/not-supported verdict is attached to E-B2; it is reported as an effect size with
  an interval.
- **Out of scope (B-full, deliberately not attempted here):** H2 ceiling/power repair (more and
  harder subjects). The instrument autopsy from Experiment 1 remains the paper's central
  contribution; Experiment B repairs the causal framing of the loop effect.

## 2. Design

- **Unit of analysis: the replicate** — one (subject, k) pair. K = 5 replicates per subject,
  4 subjects = 20 replicates; each replicate yields all three continuations from one frozen
  round 0 (60 cells, of which 20 — the `no-critic` cells — cost nothing beyond their seed).
- **Phase A — seed generation (per replicate):** one Tester call (`anthropic`,
  `claude-sonnet-5`, API-billed, provider-default sampling — draws are independent across
  replicates by sampling variance; no seed parameter exists), followed by the standard
  guardrail validation (add-only, pristine pass ×2 flake check, per-test salvage) and one
  mutation measurement. The frozen seed artifact is: (a) the accepted test file bytes, (b) the
  pristine baseline survivor set, (c) the post-round-0 survivor set S. Every seed draw is
  receipted (tokens, cost, prompt hash) whether accepted or rejected.
- **Seed rejection policy (pre-declared):** if a seed draw's tester round is rejected
  (guardrail violation, truncation) or aborted (model/network failure), that draw is receipted
  and logged, and a fresh draw is attempted — at most **3 draws per replicate** (counting every
  draw for that replicate, whatever the cause: initial rejections and any §4 replacement) and
  at most **7 total draws per subject** (K + 2 headroom). A replicate left without an accepted
  seed for **any** reason — its own 3 draws failed, or the subject cap was exhausted before it
  could draw — is scored **missing** with a `DEVIATIONS.md` entry. Rejected draws are never
  used as seeds. Draw acceptance is decided ONLY by the mechanical validity gates — never by
  the draw's kill count; the first valid draw becomes the seed, with no discretion to prefer a
  stronger or weaker one.
- **Seed freeze (mechanical):** after Phase A, the seed artifact is committed under
  `experiments/seeds/<subject>/rep<k>/` **before either paid continuation runs**. The runner
  must refuse to run a continuation unless its seed directory is committed and byte-identical
  to `HEAD` (the `assert_protocol_committed` mechanism applied to the seed path — a build
  requirement of plan step 2, tested before any paid call). Both continuations' receipts
  record the seed's SHA-256, so the shared-starting-state property is verifiable from receipts.
- **Phase B — continuations (per replicate), each starting from the frozen state on a reset
  clone:**
  - **`no-critic`** — no model calls. Outcome = the frozen round 0's own kills (baseline
    survivors minus S). Derived from the seed measurement, recorded as a first-class cell whose
    receipt references the seed. This is Experiment 1's `oneshot` arm renamed: under a shared
    round 0 the "one shot" IS the seed, and the rename prevents cross-experiment confusion.
  - **`loop-same`** — the frozen test file is injected as round 0 (no tester call; round-0
    record carries the seed hash and zero cost), re-validated, and a **reproduction check**
    runs (§4). Then Critic rounds with `anthropic`/`claude-sonnet-5`, `max_rounds = 4`,
    `dry_rounds = 2` — identical loop parameters to Experiment 1 for comparability.
  - **`loop-cross`** — same as `loop-same` with the Critic `openai`/`gpt-5.6-terra` (the
    variant id and rate verified live under Experiment 1's v8 amendment; the verified rate in
    `crucible.meter.RATES_EXTRA` carries over unchanged).
- **Ordering:** within a replicate, `loop-same` and `loop-cross` may run in either order (each
  starts from a reset clone plus the frozen seed; they share no state beyond the committed
  seed). Phase A and Phase B may be interleaved across replicates and subjects; within a
  replicate the order is strictly seed → commit → continuations. Receipts are committed per
  subject as cells complete, as in Experiment 1.
- **Tester held constant** (`claude-sonnet-5`) across all seeds; Critic lineage varies only
  between the two loop continuations.
- **Verdicts remain mechanical throughout:** a mutant is killed by pytest under mutmut or it
  survives; no model judgment enters any outcome.

## 3. Subjects

**Four subjects, unchanged from Experiment 1** — same pinned SHAs and strip-tests settings
(both read from `experiments/subjects.json`, frozen since Experiment 1 and not duplicated),
and same frozen mutmut scopes, canaries, `pytest_args`, and `also_copy` as Experiment 1
protocol_version 11 (§3.2 there; these scope blocks ARE duplicated byte-identically into
`protocol-b.json`, which the runner loads):

| Subject | Module | Experiment-1 pristine baseline survivors (counted runs) |
|---|---|---:|
| graph-guard | graph_guard/ppr.py | 22 |
| rag-guard | rag_guard/guard.py | 25 |
| packaging | src/packaging/_elffile.py | 69 |
| idna | idna/cli.py | 187 |

(The scale column is descriptive, from Experiment 1's counted per-cell table in `RESULTS.md` —
the third-party subjects are test-stripped, so their pristine baseline is their full mutant
set. Experiment B's scoring baseline is each cell's own pristine measurement, exactly as in
Experiment 1.)

**attrition-risk-ml is excluded, pre-declared, for two reasons fixed before any Experiment-B
data exists:** (1) it is the deadlock-prone subject — four failed rerun attempts under
Experiment 1, with the deadlock surviving three targeted, individually verified fixes (a
bounded-measure timeout, the joblib threading backend, native thread-pool pins) and the
residual mechanism never identified (`DEVIATIONS.md`; Experiment
1's `loop-same` cell for it is a documented MISSING cell); and (2) its degenerate 0-kill
baseline already required special-case analysis rules in Experiment 1 (§3.1 there). Losing it
costs headroom variety; keeping it risks re-suffering an unresolved instrument failure inside a
design whose whole point is clean pairing. This exclusion means Experiment B's estimates span
the four clean subjects only, and no Experiment-B claim extends to the degenerate
maximal-headroom case.

## 4. Integrity gates (in addition to Experiment 1's guardrails, all inherited)

- **Reproduction check (new, per seeded continuation):** after injecting the frozen test file
  and before any Critic call, the continuation re-measures the mutation outcome. The measured
  survivor set must equal the frozen S **exactly**. A mismatch is an instrument failure (a
  non-deterministic test slipped through the flake check, or the measurement itself is
  unstable): the continuation **fails loud and refuses to proceed** — it is never scored, and
  no plausible-zero or plausible-kill can enter the data. The mismatch is logged in
  `DEVIATIONS.md` with both survivor sets.
- **Replicate invalidation on reproduction failure:** a reproduction mismatch invalidates the
  **whole replicate** (all three continuations), because the shared-starting-state property is
  broken. The seed is retired (kept on disk, marked invalid). A replacement seed **must** then
  be drawn for that replicate if the §2 draw caps permit (it counts against both the
  per-replicate cap of 3 and the per-subject cap of 7); if the caps are exhausted, the
  replicate is scored missing. There is no discretion in either direction: replacement is
  triggered only by this mechanical instrument criterion — never by any outcome value — and is
  mandatory when triggered, so it can neither select for stronger or weaker seeds nor quietly
  drop an inconvenient replicate.
- **Seed re-validation at injection:** the frozen file re-runs the pristine validity + flake
  gate at injection time. A seed that passes at freeze time but fails at injection is the same
  instrument-failure class as a reproduction mismatch and follows the same rule.
- **A negative delta is an instrument failure, not a result.** Δ ≥ 0 holds by construction
  (add-only tests from a shared round 0), so a validly-scored continuation whose final kill
  count falls below the seed's own kills means a non-deterministic test got past both the flake
  check and the reproduction check. It is treated exactly like a reproduction mismatch:
  fail-loud, never scored, replicate invalidated, `DEVIATIONS.md` entry — never recorded as a
  negative loop effect.
- **A seed that already killed everything short-circuits.** If |S| = 0, both loop continuations
  run zero Critic rounds (the existing loop rule: no survivors before round 1 means verdict
  `clean` with no model call) and record Δ = 0 at zero marginal cost. §5 defines how such
  replicates enter the summaries.
- **Inherited from Experiment 1 unchanged:** add-only tests; rejected rounds logged with
  receipts and zero kills credited; sandbox-invalid round rejection (v5); truncation detection
  with the 32k output cap (v9); post-round tree-integrity attestation; billing guardrail
  (API-metered providers only — a Max-plan provider is refused before any run directory
  exists).

## 5. Metrics

Per replicate r, from receipts alone:

- `n_base_r` — pristine baseline survivor count; `S_r` — post-round-0 survivor set;
  `k0_r = n_base_r − |S_r|` — the frozen round 0's own kills (= the `no-critic` outcome);
  `ksame_r`, `kcross_r` — total kills of the two loop continuations.
- **Δsame_r = ksame_r − k0_r** and **Δcross_r = kcross_r − k0_r** — the critic rounds'
  incremental kills over the shared round 0 (each ≥ 0 by construction).
- **Incremental kill rate** ρsame_r = Δsame_r / |S_r| and ρcross_r = Δcross_r / |S_r| — the
  fraction of the frozen round-0 survivors that the critic rounds go on to kill. If |S_r| = 0
  (round 0 already killed everything), the rate is undefined: such replicates are reported,
  included in count-based summaries (their Δ = 0 — there was nothing left to add), and excluded
  from rate averages, with the count of such replicates stated.
- **E-B2 paired difference** D_r = Δcross_r − Δsame_r (and the rate analogue), within
  replicate.
- **Cost per incremental kill** for each loop continuation: (continuation cost) / Δ, from
  metered receipts, reported only for cells with Δ ≥ 1 (a ratio against zero kills is
  undefined). Seed cost is reported separately and never allocated to continuations —
  cross-arm cost ratios are computed **within the same subject set and same replicate set
  only** (this repairs Experiment 1's criticized cross-denominator 3.4× figure).
- Descriptives carried over from Experiment 1: rounds-to-dry, rejected/aborted round rates per
  arm, both mutation-score denominators per cell (lesson 0018), verdict distribution.

## 6. Analysis and interpretation rules (written before any data)

- **Primary readout (E-B1): effect size with uncertainty interval, not a p-value gate.**
  Per subject: the mean of Δsame_r and of ρsame_r over its K replicates, each with a 95%
  percentile bootstrap interval over replicates (resampling replicates within subject, 10,000
  draws, RNG seed **20260713** — fixed here and in `protocol-b.json`'s `analysis` block, not
  left to `analyze.py`, which is editable after data lands). Pooled: the **unweighted mean of
  the four subject means** (each subject contributes equally regardless of its mutant count),
  with a subject-level cluster bootstrap interval (resampling subjects with replacement, same
  seed).
  With 4 clusters this interval is wide and coarse; that is disclosed in §9 rather than
  papered over with a finer-grained method whose independence assumptions the data would
  violate.
- **No pooled per-mutant McNemar as a confirmatory statistic.** Experiment 1's pooled-mutant
  McNemar treated mutants as independent units; under replicates that ignores both
  within-subject and within-replicate clustering. Per-mutant paired tables may appear in an
  appendix explicitly labeled descriptive; they license no claim.
- **Interpretation of E-B1 (licensed statements, fixed now):**
  - The paper's causal claim is licensed at the level of this design: "starting from an
    identical frozen round-0 suite, same-lineage critic rounds killed an additional X% of
    remaining survivors on average (95% interval [a, b])." If the pooled interval's lower
    bound is > 0, the loop's incremental effect is claimed as positive; the claim's strength
    is the magnitude and interval, never a standalone p-value.
  - If Δsame ≈ 0 throughout (pooled mean ρsame with interval upper bound < 0.10), the honest
    conclusion is that Experiment 1's H1 gap was dominated by round-0 sampling variance rather
    than the loop — this outcome is publishable and will be reported with the same prominence
    (blind-oracle-pilot posture, carried over).
  - These two statements are bands of ONE readout, not alternatives to choose between. Because
    Δ ≥ 0 by construction, a positive lower bound is cheap, so the two bands can **both** hold
    (e.g., interval [0.02, 0.08]): in that case the licensed conclusion is "positive but
    small — most of Experiment 1's gap was round-0 sampling variance," and both statements are
    made together. There is no discretion to report only the flattering band.
  - Any comparison to Experiment 1's b=105/c=0 figure is framed as confounded-vs-causal — the
    Experiment-B estimate supersedes it as the loop-effect claim; Experiment 1's H1 is
    described going forward as a pipeline-level observation.
- **Interpretation of E-B2 (pilot):** report the pooled mean D with its cluster-bootstrap
  interval and per-subject means. No supported/not-supported verdict; no lineage-effect claim
  in either direction beyond "consistent/inconsistent with a cross-lineage advantage at this
  scale." The bundling of model+provider+harness in "lineage" is restated wherever E-B2 is
  discussed.
- **No subgroup hunting.** The only breakdowns are: per-subject, pooled-across-4-subjects, and
  the pre-declared count/rate variants above. Anything else is labeled post-hoc exploratory
  and never substituted for the primary readout.
- **Missing replicates** (all seed draws failed, or invalidated without a replacement within
  the draw caps) are reported as missing, never imputed; `analyze.py` extends the Experiment-1
  missing-cell guard so a missing replicate can never contribute kills to any summary.
- **Partially missing replicates are handled per estimand.** Each estimand uses exactly the
  replicates in which **all of its required cells are valid**: E-B1 requires a valid seed and a
  valid `loop-same` continuation; E-B2 requires a valid seed and **both** valid loop
  continuations. A replicate can therefore contribute to E-B1 but not E-B2 (e.g., its
  `loop-cross` cell aborted twice). The replicate composition of every reported estimate is
  stated wherever that estimate appears.

## 7. Exclusions and deviations

Inherited verbatim from Experiment 1 §6: invalid/flaky generated tests are logged and never
counted as kills; aborted continuations are missing cells documented in `DEVIATIONS.md`; reruns
happen only with a `DEVIATIONS.md` entry and always into a fresh receipted run directory. One
addition: an aborted **continuation** (model failure mid-critic-rounds) **is rerun exactly
once** from its committed seed, with a deviation entry — the seed is frozen state, so a
continuation rerun does not resample round 0 and does not break pairing; its partner
continuation is unaffected. If the rerun also aborts, that cell is missing (no further
attempts, no discretion). The rerun is mandatory, not optional, so a partially-observed
outcome can never influence whether the cell gets its second attempt.

## 8. Stopping rules

- **Exactly K = 5 replicates per subject**, fixed in `protocol-b.json`. No early stopping on
  any result, no additional replicates in search of a tighter interval or larger effect, no
  re-running a validly scored continuation. The only additional draws permitted are the
  seed-rejection and invalidation replacements of §2/§4, capped at 7 draws per subject total.
- Per-cell loop stopping is unchanged from Experiment 1: `dry_rounds = 2`, `max_rounds = 4`.
- The flake check remains the 2-run check, with the same disclosed residual-flake limitation;
  the new reproduction check (§4) now catches downstream what the flake check misses upstream,
  for the seed file specifically.

## 9. Limitations (written before data)

- **Four subjects, five replicates.** The cluster-bootstrap interval over 4 subjects is coarse;
  per-subject intervals over 5 replicates are individually weak. Experiment B buys causal
  cleanliness, not power — that trade is deliberate and priced (§10). Generalization beyond
  these four modules is not claimed.
- **Δ ≥ 0 by construction for E-B1.** The design cannot observe a negative loop effect (tests
  are add-only). The pre-registered question is magnitude; "the loop adds nothing" (Δ ≈ 0) is a
  fully reportable outcome.
- **Seed draws are sampling-variance replicates, not controlled seeds.** The provider exposes
  no RNG seed; replicates capture round-0 draw variance by independent sampling, which is the
  point — but two replicates can by chance draw similar suites, and K = 5 cannot characterize
  the draw distribution's tails.
- **E-B2's "lineage" bundles model, provider API behavior, and harness interaction** (the
  Experiment-1 truncation autopsy is the standing proof that harness asymmetry can masquerade
  as a lineage effect). The 32k cap + truncation detection reduce but do not eliminate this
  class; E-B2 stays a pilot partly for this reason. One known, unrepaired harness asymmetry is
  named now: the Anthropic critic path uses a 1200s HTTP read timeout (`LongAnthropicProvider`,
  Experiment 1 commit `ed0164a`) while the OpenAI critic keeps the 300s default (its counted
  replies ran 431–4,566 output tokens across the final counted set (`RESULTS.md`), nowhere near
  timeout scale — the asymmetry was introduced in `DEVIATIONS.md`'s graph-guard v9 rerun row).
  Resource parity across providers is disclosed, not enforced.
- **Training-data contamination**, **hostile-test harness detection**, and the **2-run flake
  check** limitations carry over verbatim from Experiment 1 §8; the reproduction check narrows
  the flake exposure for the seed file only, not for critic-round tests.
- **Single tester lineage.** All seeds come from `claude-sonnet-5`; nothing is claimed about
  other tester models.

## 10. Budget

- Every round is metered exactly as in Experiment 1 (`crucible.meter.cost_usd`; unpriced models
  fail closed). Receipts land under `experiments/runs-b/` (Experiment 1's `experiments/runs/`
  is frozen and untouched) and are committed per subject as cells complete; frozen seeds land
  under `experiments/seeds/`.
- Paid calls: 20 accepted seed draws (plus up to 8 rejected-draw retries across all subjects at
  the caps) + 40 seeded continuations × up to 4 critic rounds. Estimate **$15–30** all-in,
  based on Experiment 1's counted per-cell costs; the `no-critic` cells are free by
  construction. There is no hard mid-run tripwire (Experiment 1 posture: results over pennies,
  everything receipted), but Phase A does not begin until the operator (Jeff) explicitly
  approves the spend, and a running total is visible in receipts at every commit.
- `gpt-5.6-terra`'s rate was live-verified under Experiment 1's v8 amendment; no re-verification
  is required unless the pricing page changes before the first `loop-cross` call, in which case
  the v8 procedure repeats and the check is recorded here by amendment.

## 11. Approval

Approved by: Jeff Otterson, 2026-07-13 (interactive gate; scope knob K=5 on the 4 clean
subjects set by Jeff at session start, 2026-07-13)

Amendments after this freeze follow Experiment 1's convention: appended to this file with a
version bump to `protocol_b_version`, marked PRE-DATA or with the exact affected cells named,
each requiring the operator's explicit approval recorded in the amendment text.
