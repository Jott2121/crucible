# PROTOCOL — Crucible Experiment (H1 replication, H2 novel claim)

Status: **PRE-REGISTERED — written before any paid run.** The `crucible experiment` command
(`src/crucible/experiment.py::assert_protocol_committed`) mechanically refuses to run any arm
unless this repo's `experiments/protocol.json` is committed and byte-identical to `HEAD`, so the
freeze is enforced by tooling, not by promise. Every number in the eventual `RESULTS.md` must be
recomputable from the committed receipts under `experiments/runs/`.

Repo: `ai-agentic-code-testing`, branch `feat/experiment`. Companion files: `experiments/protocol.json`
(machine-readable arms config `crucible experiment` loads), `experiments/DEVIATIONS.md` (append-only
log of any post-freeze departure), `docs/RELATED-WORK.md` (the claim ledger this document cites).

## 1. Claim under test

### H1 — replication, not priority

> **Claim.** The adversarial loop (Tester round 0, then a Critic round per named survivor) kills
> more mutants than one-shot test generation, same tester model, same subject-module, with costs
> disclosed.

H1 is framed strictly as a **replication in a new setting**, per `docs/RELATED-WORK.md` Claim 4.
The claim-boundary paragraph that document ends on, quoted verbatim here as the binding scope
statement for this protocol:

> "To our knowledge, no prior work measures the effect of critic-generator lineage diversity
> (cross-lineage vs. same-lineage) on test-suite fault detection under a mechanical mutation-kill
> oracle, nor reports LLM test-generation cost normalized per killed mutant or per detected fault; the
> closest systems either share a single model backbone across adversarial roles (AdverTest, arXiv
> 2602.08146), assert cross-family benefit without a controlled ablation in a different domain
> (Refute-or-Promote, arXiv 2604.19049, defect discovery, "no ablation studies"), or report cost per
> file or per method-run rather than per outcome (TestForge, arXiv 2503.14713; AdverTest). We do not
> claim to be first to run an adversarial test-vs-mutant loop under a mechanical oracle (AdverTest
> already does this), first to feed survivor mutants into LLM prompts (MuTAP already does this), or
> first to pre-register an empirical software-engineering protocol (established precedent exists,
> arXiv 2302.03649, arXiv 2606.10702). We claim only: the first controlled measurement of cross-lineage
> vs. same-lineage critic effect under a mechanical oracle, the first cost accounting normalized per
> killed mutant / per detected fault in this literature, and a replication of the MuTAP-to-AdverTest
> adversarial-loop direction in a new agentic, repo-level, Python setting with disclosed costs."

Concretely: MuTAP established survivor-feedback into prompts (single-agent, benchmark-scale,
Codex/Llama-2); AdverTest established a dual-agent adversarial test-vs-mutant loop under a
mechanical oracle with measured gains (+8.6% relative FDR over HITS on Defects4J/GrowingBugs).
This project's H1 is not a new pattern — it is that pattern replicated in an agentic, repo-level,
Python setting with disclosed per-outcome costs, which the ledger's Claim 2 sweep found unreported
anywhere in prior work.

### H2 — the novel claim

> **Claim.** A cross-lineage Critic (GPT-5.6, `openai`) kills more of the survivors a same-lineage
> Tester (Claude Sonnet 5, `anthropic`) missed than a same-lineage Critic (Claude Sonnet 5) does,
> under the same mechanical mutation-kill oracle.

H2 is the claim `docs/RELATED-WORK.md` Claim 1 confirms **CONFIRMED OPEN** after a seven-phrasing
adversarial novelty sweep. The two nearest-miss systems, both full-text verified and both falling
short of measuring this:

- **AdverTest (arXiv 2602.08146)** — the closest in-domain system: an adversarial test-vs-mutant
  loop under a genuinely mechanical oracle. But both its Tester and Mutant agents share **one
  backbone per configuration** ("DeepSeek-v3.2, GPT-OSS-120B for both agents," §4.4) — no
  cross-lineage vs. same-lineage comparison is ever run within a configuration.
- **Refute-or-Promote (arXiv 2604.19049)** — uses a Cross-Model Critic (CMC) and argues
  cross-family review "can catch correlated blind spots that same-family review misses," but (a)
  its domain is vulnerability/defect discovery, not test generation; (b) it states explicitly "no
  ablation studies isolating individual mechanisms" — the cross-lineage benefit is asserted from
  n=2 anecdotal cases, not measured against a same-lineage control; (c) its verdict blends LLM
  judgment with a partially mechanical PoC gate, not a pure mechanical oracle.

Either direction of result is publishable and pre-declared as such (§4): a measured cross-lineage
advantage, a null (same-lineage performs statistically indistinguishably, or better — `Self-MoA`
found same-model repeated sampling beating heterogeneous mixture-of-agents by 6.6% on reasoning
benchmarks, so the direction is genuinely open, not assumed in our favor per the ledger).

## 2. Design

- **Unit of comparison:** one subject-module, paired across arms. Every arm runs against the
  *same* pinned subject clone and module, so per-mutant kill outcomes can be paired mutant-for-mutant
  across arms (McNemar requires paired discordant counts, §5).
- **Arms** (exact machine-readable config in `experiments/protocol.json`):
  - `oneshot` — Tester writes tests once (round 0 only), no Critic round.
  - `loop-same` — Tester round 0, then Critic rounds where the Critic is the **same lineage**
    as the Tester (`anthropic`/`claude-sonnet-5`).
  - `loop-cross` — Tester round 0, then Critic rounds where the Critic is a **different
    lineage** (`openai`/`gpt-5.6`).
- **Tester model, held constant across all three arms and all subjects:** `anthropic`,
  `claude-sonnet-5`.
- **Rounds:** `max_rounds = 4`, `dry_rounds = 2` (a run stops when 2 consecutive rounds kill
  nothing new, or at 4 rounds, whichever comes first — see `crucible.loop._run`).
- **Verdicts are mechanical throughout:** a mutant is killed by pytest under mutmut or it
  survives; no model ever judges its own or another model's output (design principle, spec §1).
- **Pilot rule (pre-declared):** graph-guard is the pilot subject (spec §8 sequencing, plan Task
  5, go/no-go gate before the full grid runs). Its pilot cells (`oneshot`, `loop-same`) **count
  as its H1 cells** — they are not discarded or rerun once the pilot passes go/no-go. This is
  decided here, before any pilot data exists, per the plan's default ("pilot cells count unless
  DEVIATIONS says otherwise").

## 3. Subjects

Five subjects, pinned by SHA (`experiments/subjects.json`), each contributing one paired
subject-module cell to every arm. Smoke-run mutant counts below are from the selection-time smoke
run (`experiments/subjects.json`), not the pre-registered run itself — they establish the
denominator scale each subject is expected to fall near, not the final measured baseline (the
baseline used for scoring is the pristine measurement `crucible.loop._run` takes before any
generated test exists, per subject-module, at run time).

| Subject | Source | Module | Smoke mutants | Smoke killed | Smoke survived |
|---|---|---|---:|---:|---:|
| attrition-risk-ml | local:~/attrition-risk-ml | src/train.py | 255 | 0 | 255 |
| graph-guard | local:~/graph-guard | graph_guard/ppr.py | 80 | 58 | 22 |
| rag-guard | local:~/rag-guard | rag_guard/guard.py | 71 | 45 | 26 |
| packaging | pypi-git (pypa/packaging) | src/packaging/_elffile.py | 69 | 36 | 33 |
| idna | pypi-git (kjd/idna) | idna/cli.py | 187 | 126 | 61 |

All third-party subjects (`packaging`, `idna`) have their existing test suites stripped in the
local clone before any run (`strip_tests: true`), so the loop is scored against a genuinely empty
starting suite — never against the upstream project's own tests. Local subjects
(`attrition-risk-ml`, `graph-guard`, `rag-guard`) keep their existing suites (`strip_tests: false`)
per `experiments/subjects.json`.

### 3.1 attrition-risk-ml's zero-kill baseline — the degenerate maximal-headroom false-pass case

attrition-risk-ml's smoke run killed **0 of 255 mutants** with its existing test suite —
`src/train.py` has full mutant headroom before any generated test runs (its only test file,
`tests/test_data.py`, never imports `train`; every mutant survives by default). This is a
**degenerate** baseline, qualitatively different from every other subject (next-lowest kill rate
is packaging at 36/69 = 52%): it is the **maximal-headroom false-pass case** — a suite that looks
present but catches nothing — which is exactly the failure mode this project's `graph-guard`
origin work (spec §1, oracle-gate lineage) exists to catch. It is kept **deliberately**, not
excluded, because it is directly thesis-relevant.

Its degenerate baseline imposes pre-declared analysis constraints, fixed here before any data
exists (binding rules restated in §4):

- **Never included in any relative-improvement metric.** Any ratio computed against a 0-kill
  baseline is undefined, and any intervention trivially "wins" against zero — a
  relative-improvement figure for this subject would be meaningless by construction. Only
  **absolute** kill counts and kill rates are reported for attrition-risk-ml.
- **Reported per-subject, and pooled both with and without it.** Its 255 paired outcomes would
  numerically dominate a pooled 2x2 (255 of ~660 smoke mutants across the five subjects), so the
  pooled McNemar for both H1 and H2 is reported in **all three pre-declared views** (§4):
  pooled-with-attrition, pooled-without-attrition, and the five per-subject tables. All three
  views are committed to in advance so no view can be chosen after seeing results.

### 3.2 Run configuration — frozen mutmut scopes

The measurement configuration is part of this pre-registration, not a run-time choice: each
subject's `[tool.mutmut]` scope — `source_paths` (exactly the target module) **and** its
`also_copy` entries, as recorded in `experiments/subjects.json` and the Task 3 fix report — is
frozen here as the exact scope every arm's runs will use. Fresh prep re-clones wipe the throwaway
smoke configs by design, so the real runs re-apply exactly these scopes:

| Subject | `source_paths` | `also_copy` | Scope notes |
|---|---|---|---|
| attrition-risk-ml | `["src/train.py"]` | `["src", "data"]` | tests read `data/hr_attrition.csv`; suite = `tests/test_data.py` only |
| graph-guard | `["graph_guard/ppr.py"]` | `["graph_guard"]` | `tests/test_ppr.py`; `test_sparql_vs_ppr.py` excluded (imports the repo's top-level `eval` package, unresolvable inside mutants/) |
| rag-guard | `["rag_guard/guard.py"]` | `["rag_guard"]` | `tests/test_guard.py` |
| packaging | `["src/packaging/_elffile.py"]` | `["src/packaging"]` | dev-test deps `pretend`, `tomli_w` required for collection; editable install replaces the venv's PyPI `packaging` dist (pytest's own dependency) |
| idna | `["idna/cli.py"]` | `["idna"]` | no extra deps; `tests/test_idna_cli.py` collects cleanly |

Only the `source_paths` module is ever mutated; `also_copy` entries are carried into mutmut's
mutants/ tree **unmutated**, so in-package sibling imports and pytest's own transitive imports
resolve. Any departure from these scopes at run time is a protocol deviation and requires a
`DEVIATIONS.md` entry (§6).

**Amendment (protocol_version 2, PRE-DATA, made after pilot attempt 1 crashed before any model
call — see `DEVIATIONS.md`):** the table above was frozen as prose only; `crucible experiment`'s
`SubjectEnv.preflight` wrote only `source_paths` into the clone's `[tool.mutmut]`, never the
`also_copy` entries, so mutmut's sandbox could not import the package and every mutant reported
`not checked`. The content of the table is unchanged — `experiments/protocol.json` now carries it
machine-readable under a `"subjects"` map (one entry per clone-dir name: `module`, `also_copy`,
and, for graph-guard, `pytest_args` excluding `test_sparql_vs_ppr.py`), and `crucible.experiment
.run_arm` threads it into `SubjectEnv`/`write_scope` so the frozen scope is what actually runs.
This amendment happened before any paid model call was made against any subject, so no data is
affected.

**Amendment (prompt templates bumped to v2, PRE-DATA):** prompt templates bumped to v2 after
pilot shakeout — pilot attempt 2's two graph-guard cells (both verdict rejected at round 0, zero
kills, receipts preserved) revealed a numeric-assertion gap in the tester prompt; ALL counted
cells run under the v2 prompts (uniform bar). `src/crucible/prompts/tester.md` and
`src/crucible/prompts/critic.md` each gained two rules: never assert exact floating-point
equality (use `pytest.approx`), and mentally execute the generated test file top to bottom before
finishing so it is guaranteed to collect cleanly under pytest. The v2 prompt sha256 hashes are
recorded here: `tester 9235e2f3fb8cfc3c`, `critic bdacfa09451a7220` (16-char prefixes, computed via
`crucible.roles.build_tester_prompt`/`build_critic_prompt`). Prompt-v2 amendment approved by Jeff
Otterson 2026-07-10 (interactive gate).

**Amendment (protocol_version 3 — per-test salvage, artifact preservation, prompt v3, PRE-DATA):**
the v2 pilot cells were still all-or-nothing at the validity gate: a graph-guard file with 13
pristine-passing tests died entirely because 1 test computed its expected value from a different
PageRank convention than this pinned subject uses (a wrong-oracle test, not a bad file). Mutation-
testing convention treats the pinned subject as ground truth at baseline, so a pristine-failing
test is droppable as an invalid oracle for that one test, not a reason to reject 12 good tests
alongside it — and the drop is itself interesting data (which convention the model assumed), so it
is logged, never silently discarded.

- **Per-test salvage.** `crucible.guardrails.validate_new_tests` (all-or-nothing) is kept for
  compatibility; `SubjectEnv.validate` now calls the new `crucible.guardrails.salvage_new_tests`,
  which runs the generated file on pristine code, and on red parses the pytest failure summary for
  the specific failing test name(s), removes exactly those `FunctionDef` nodes (AST parse/
  unparse), and re-validates (pass, then flake-check) the pruned file. A pristine-failing test is
  **dropped, never counted as a kill in any metric in §4**, and the round's `dropped_tests` field
  (new on `RoundRecord`) records which test(s) were dropped, per round, in every receipt.
  `crucible.runner.run_tests` now passes `-rf` so the "FAILED path::name" summary line the parser
  depends on cannot be suppressed by a subject's own pytest addopts/ini.
- **Rejected-artifact preservation.** `SubjectEnv.set_artifact_dir(run_dir)` (called by
  `crucible.experiment.run_arm` right after the receipt writer is created, before any round runs)
  makes a rejected test file land at `<run_dir>/rejected/<label>-<filename>` instead of being
  unlinked, and the pre-salvage original of a pruned file lands at
  `<run_dir>/salvaged/<filename>.orig` before pruning. Every rejected or salvaged-away test file
  from every counted cell is therefore preserved evidence under `experiments/runs/`, not lost.
- **One new prompt line.** `src/crucible/prompts/tester.md` and `src/crucible/prompts/critic.md`
  each gained: "For algorithmic/numeric code where the exact convention is ambiguous from the
  signature and docstring alone, prefer asserting provable properties (ranges, sums, orderings,
  invariants) over exact computed constants." — a direct response to the graph-guard wrong-oracle
  case (a different PageRank convention is exactly this kind of ambiguity). ALL counted cells run
  under prompt v3 (uniform bar, same rule as the v2 bump).
- **graph-guard v2 cells reclassified.** The two graph-guard cells run under prompt v2
  (`experiments/runs/graph-guard/oneshot-20260710T164217Z/`,
  `experiments/runs/graph-guard/loop-same-20260710T164442Z/`, $0.37 total, both verdict rejected at
  round 0 — one zero-collection, one wrong-oracle 1-of-14 test) are reclassified as shakeout under
  this amendment, same as pilot attempt 2's v1 cells: not counted data. graph-guard's counted cells
  will be fresh runs under prompt v3 with salvage active, so the wrong-oracle test is dropped and
  logged instead of failing the whole file. Total shakeout spend is now $0.73 across 4 cells (see
  `DEVIATIONS.md`).
- **Prompt v3 sha256 hashes.** Computed via `crucible.roles.build_tester_prompt`/
  `build_critic_prompt` against this repo's own fixture module (`module_path="subject_pkg/calc.py"`,
  `module_source=` the contents of `tests/fixtures/subject/subject_pkg/calc.py`, `survivor_diffs={}`
  for the critic) — a fixed, reproducible-from-repo canonical input, not any real subject's content
  (a real subject's hash necessarily varies with that module's source, so it cannot serve as a
  version identifier by itself): `tester 98abbb8532990865`, `critic 703335c0af111836` (16-char
  prefixes).

v3 amendment approved by Jeff Otterson 2026-07-10 (interactive gate).

**Amendment (protocol_version 4 — scope transcription corrections after free dry-run
validation caught mismatches; zero counted cells affected, all failures pre-model, $0):**
the H1 grid's first pass hit all-`not checked` mutant status (identical failure class to
pilot attempt 1, §3.2's protocol_version-2 amendment) on 4 of 5 subjects — `rag-guard`,
`idna`, `packaging`, `attrition-risk-ml` — every one of it before any model was ever
called (8 cells, $0 total; `graph-guard`'s two cells, run first, were unaffected and stand
as counted data). `experiments/validate_scopes.py` (new, stdlib-only, $0) was built to
reproduce and fix all four for free before any further paid cell runs, and diagnosis found
two distinct root causes, not one:

- **`rag-guard`: a real scope-transcription gap.** §3.2's table always named
  `tests/test_guard.py` as the scope's test selection in prose, but `experiments/
  protocol.json`'s machine-readable `subjects` map (the config `SubjectEnv.preflight`
  actually writes) never carried a `pytest_args` entry for it — unlike `graph-guard`,
  which does exclude `test_sparql_vs_ppr.py` this way. Without it, mutmut's baseline
  stats phase collects the WHOLE `tests/` dir, including `tests/test_hook.py`, which
  imports a top-level `bin` package never in `also_copy` (`ModuleNotFoundError: No module
  named 'bin'`) — a genuine collection error, not a design tradeoff. Fixed:
  `protocol.json`'s `rag-guard` entry now carries `"pytest_args": ["tests/test_guard.py"]`,
  matching the smoke config recorded in `.superpowers/sdd/task-3-fix-report.md`. Verified:
  71 mutants / 45 killed / 26 survived — exact match to the recorded smoke count.
- **`idna` and `packaging`: not a scope bug — a real mutmut/tooling limitation with the
  "genuinely empty starting suite" design.** Both are `strip_tests: true` subjects whose
  entire `tests/` directory is removed before any cell runs (§3, "scored against a
  genuinely empty starting suite"). mutmut's own baseline "Running stats" phase is a bare
  pytest run over the whole subject; with zero test files anywhere, pytest exits 5 ("no
  tests ran"), and mutmut treats that as a hard failure ("failed to collect stats. runner
  returned 5") rather than reporting 0% coverage — every generated mutant is left at
  status `not checked` forever, which `oracle_gate.survivors.undetected` correctly refuses
  to classify (fail-closed by design). No `[tool.mutmut]` scope change can fix this: it
  reproduces identically once `packaging`'s separate preflight blocker (below) is cleared.
  Fixed at the engine level, not the config level: `crucible.engine.MutmutEngine.measure`
  (`_zero_test_baseline`) now recognizes this exact precondition — ALL generated mutants
  "not checked" AND a bare, unscoped `pytest -q --ignore=mutants` confirming either zero
  tests exist anywhere (exit 5) or a real, passing suite that simply never executes the
  mutated module (exit 0, e.g. `attrition-risk-ml`'s pre-declared §3.1 degenerate case) —
  and returns every mutant as an undetected survivor by construction (mechanically proven,
  not guessed), instead of raising. Any other cause of `not checked` (a real collection
  error, a partial mix of `not checked` and classified statuses) still fails loud;
  `validate_scopes.py` is the second line of defense, since a wrong-file scope would also
  disturb the mutant COUNT it checks. Verified: `idna` 187 mutants (exact match to smoke's
  denominator; 0 killed / 187 survived vs. smoke's 126/61, expected — smoke was measured
  against `idna`'s own unstripped suite at selection time, not the real empty-suite
  baseline); `packaging` 69 mutants (exact match; 0/69 vs. smoke's 36/33, same reason).
- **`packaging` additionally: a preflight-level config bug, separate from the above.** The
  strip (`git rm -rq tests`) left a dangling `testpaths = ["tests"]` in `packaging`'s own
  `[tool.pytest.ini_options]`; pytest issues `PytestConfigWarning: No files were found in
  testpaths` at config time, and `packaging`'s own `filterwarnings = ["error"]` escalates
  that warning into a hard collection-time crash (`pytest` exit 2, not the honest exit 5
  `SubjectEnv.preflight` expects from a stripped subject). `experiments/prep.py`'s own
  smoke check already silenced this with `-W ignore::pytest.PytestConfigWarning`, but
  `crucible.runner.run_tests` (what `SubjectEnv.preflight` actually calls at cell time)
  carries no such flag, so this was a hard stop before any model call. Fixed in the clone
  (`~/crucible-subjects/packaging/pyproject.toml`, stale `testpaths` line removed, commit
  `crucible: drop stale testpaths after strip`) and in `experiments/prep.py`
  (`drop_stale_testpaths`, runs automatically after every future strip, only when the
  removed line names exactly the directory that strip deleted). Verified: fresh
  `prep.py --only packaging` reproduces the fix with no manual step.
- **`attrition-risk-ml`: the clone has no `pyproject.toml` at all** (not a third-party
  `pypi-git` subject; nowhere for mutmut to read `[tool.mutmut]` from), so
  `crucible.engine.write_scope` raised `ScopeError` before any model was ever called.
  Fixed: `write_scope` gained `create_if_missing: bool = False`; when `True` and the file
  is absent, it creates a minimal file carrying ONLY the `[tool.mutmut]` table (comment:
  "created by crucible preflight — mutmut scope only" — crucible never invents real
  project metadata for a disposable clone). `SubjectEnv.preflight` now always passes
  `create_if_missing=True`. Verified: 255 mutants / 0 killed / 255 survived — exact match
  to smoke (§3.1's pre-declared degenerate zero-kill case; both smoke and the real
  baseline measure the same zero-coverage state, so the split matches exactly here, unlike
  `idna`/`packaging`).

`experiments/validate_scopes.py` reuses the real `crucible.env.SubjectEnv` (`reset_clone`
+ `preflight`, `FakeProvider`, never a real model call) and `crucible.engine.MutmutEngine.
measure` for all five subjects, comparing measured `(mutants, killed, survived)` against
`subjects.json`'s recorded smoke counts, and is the free dry-run gate that should have
existed before the H1 grid ran. All five subjects verified MATCH (`graph-guard` and
`attrition-risk-ml` and `rag-guard` exactly; `idna`/`packaging` on mutant count, with the
killed/survived split legitimately differing as designed — see above). The content of
§3.2's frozen-scope table is otherwise unchanged; this amendment corrects the machine
transcription and the tooling gaps discovered exercising it, not the pre-registered
design. Zero counted cells are affected: all 8 failed attempts across the 4 subjects were
pre-model, $0 (`experiments/DEVIATIONS.md`).

v4 amendment: config/engine/tooling fix, not an interactive-gate design change (no arm,
subject, or metric definition changed) — applied under the same "PRE-DATA, before any
paid cell for these subjects" standing as the v2 amendment.

## 4. Metrics

- **Primary statistic — per-mutant paired kill outcomes, exact McNemar, two-sided.** Implemented
  in `crucible.report.mcnemar_exact(b, c)`: two-sided exact McNemar on the discordant pair counts
  (`b` = killed by arm A only, `c` = killed by arm B only), computed as
  `min(1.0, 2 * sum(comb(n, i) for i in range(min(b,c)+1)) / 2**n)` with `n = b + c` (min-tail
  doubling of the exact binomial tail, `n=0` defined as `p=1.0`). Pairing is over the union of
  each arm's pristine baseline survivors (`crucible.report._baseline` — round 0's
  `survivors_before`, measured before any generated test exists), so both arms are scored against
  the same discordant-pair universe (`crucible.report.paired_kills`).
- **Reported in three pre-declared views: pooled-with, pooled-without, and per-subject.** H1's
  comparison (`loop-same` vs `oneshot`) and H2's comparison (`loop-cross` vs `loop-same`) are each
  reported as (a) one pooled McNemar across all five subjects' discordant pairs
  (**pooled-with-attrition**), (b) one pooled McNemar across the four subjects excluding
  attrition-risk-ml (**pooled-without-attrition** — its 255 paired outcomes would otherwise
  numerically dominate the pooled 2x2, §3.1), and (c) five separate **per-subject** McNemar
  tables. All three views are committed to here, in advance, and all three appear in RESULTS.md
  for both hypotheses — no view is chosen, promoted, or dropped after seeing results.
- **attrition-risk-ml is never included in relative-improvement metrics.** Per §3.1, any ratio
  against its 0-kill baseline is undefined and any intervention trivially wins; for this subject
  only **absolute** kill counts and kill rates are reported (its per-mutant paired outcomes still
  enter the pooled-with-attrition McNemar view and its own per-subject table, which are
  discordant-count statistics, not baseline-relative ratios).
- **Survivors killed** — count and rate, per arm, per subject (`crucible.report.summarize`).
- **Cost-per-kill from receipts.** `total_cost_usd / killed` per run (`crucible.report.summarize`,
  `cost_per_kill` field), computed from the meter's exact per-round `input_tokens`/`output_tokens`
  cost (`crucible.meter.cost_usd`), never estimated. Per `docs/RELATED-WORK.md` Claim 2, no prior
  work in this literature normalizes cost to an outcome — AdverTest reports $0.270/method-run
  (Defects4J/DeepSeek) and TestForge reports $0.63/file, but neither divides by kills or faults;
  this project's cost-per-kill is the first such per-outcome figure in this literature, and is
  reported for that reason with no discretion to omit it for any cell that produced at least one
  kill.
- **Full-denominator mutation scores, reported both ways.** Per lesson 0018 (spec §8): (a) mutation
  score against the pristine-baseline survivor count only (the mutants a suite could plausibly
  still kill going in), and (b) mutation score against the subject's full mutant count including
  mutants already killed pre-baseline by an existing suite (relevant to the three local subjects,
  which are not test-stripped). Both denominators are printed for every cell; neither is presented
  alone.
- **Rounds-to-dry** and **invalid/flaky rates per arm** (spec §8) are reported descriptively
  alongside the above, not as a hypothesis test.

## 5. Success criteria and null interpretation (written before data)

These interpretation rules are fixed now, before any paid run, and are not revisited after seeing
results.

The confirmatory pooled test for both hypotheses is the **pooled-with-attrition** view (all five
subjects, §4) — fixed here so the existence of the pooled-without-attrition view can never be used
to swap the decision statistic after the fact. The pooled-without-attrition and per-subject views
are pre-declared companion readouts, always reported alongside the verdict; if the
pooled-without-attrition view disagrees with the confirmatory verdict, that disagreement is
reported prominently as a robustness finding, but it does not change the supported/not-supported
call defined below.

- **H1 supported** if and only if the **pooled** McNemar test (H1 comparison: `loop-same` vs
  `oneshot`, discordant pairs across all five subjects) yields **p < 0.05**, **and** the direction
  favors `loop-same` (more mutants killed by `loop-same` than by `oneshot` among the discordant
  pairs, i.e. `b > c` where `b` = loop-same-only kills). Any other outcome — p ≥ 0.05, or p < 0.05
  in the opposite direction — is **not supported**. Effect sizes (kill-rate deltas, per-subject
  and pooled) are reported regardless of significance; a non-significant or reversed result is
  written up with the same prominence as a supported one (blind-oracle-pilot posture, spec §8).
- **H2 supported** if and only if the **pooled** McNemar test (H2 comparison: `loop-cross` vs
  `loop-same`, discordant pairs across all five subjects) yields **p < 0.05**, **and** the
  direction favors `loop-cross` (more mutants killed by `loop-cross` than by `loop-same` among the
  discordant pairs). Any other outcome is **not supported**; a null here is itself the second
  publishable finding named in §1 ("mechanical oracles shown to reduce the need for [a
  cross-lineage critic]," spec §8) and is reported with the same prominence as a supported result.
- **No subgroup hunting beyond the pre-declared views.** The only breakdowns are the three views
  already specified in §4 (pooled-with-attrition, pooled-without-attrition, and the five
  per-subject McNemar tables). No additional slicing (by module type, by arm ordering, by round number, or any
  other post-hoc grouping) is performed in search of significance; if such a breakdown is later
  judged useful for discussion, it is reported explicitly labeled as **post-hoc, exploratory, not
  a pre-registered test** and never substituted for the primary pooled/per-subject readout above.

## 6. Exclusions

- **Invalid or flaky generated tests are logged, never counted as kills.** A test that fails
  `crucible.guardrails` validation (does not compile/collect, or does not pass on the pristine
  module twice — the flake check, §7) is rejected before it can contribute a kill; the round is
  recorded with `status="rejected"` and the rejection reason in the receipt, and the round's
  `survivors_after` is left equal to `survivors_before` (`crucible.loop._round`). No invalid or
  flaky test is ever counted toward a kill in any metric in §4.
- **Aborted runs are a missing cell, documented in `experiments/DEVIATIONS.md`.** If a round
  aborts (model call failure after env-level retries, or a post-round integrity check failure —
  `crucible.loop._round` status `"aborted"`), the run's verdict is `"aborted"` and that
  (arm, subject) cell is treated as missing data, not as a zero. It is never silently backfilled
  or estimated; it is logged in `DEVIATIONS.md` with subject, arm, timestamp, and cause.
- **Reruns only with a `DEVIATIONS.md` entry.** A red or aborted run is data, never silently
  rerun. Any rerun gets a new run directory (receipts are append-only and never overwritten) and a
  corresponding row in `DEVIATIONS.md` stating what failed, why, and that a rerun followed.

## 7. Stopping rules

- Each arm runs **exactly once per subject** under this protocol (3 arms × 5 subjects = 15 cells
  total). There is no early stopping for significance and no re-running a cell that produced a
  valid verdict (`clean`, `dry`, or `cap`/`oneshot`) in search of a better outcome.
- A generated test file must pass on the pristine subject module **twice** before it is accepted
  (the flake check in `crucible.guardrails`; a test that passes once then fails is rejected as
  `"flaky"`). This is a 2-run check by deliberate choice, not exhaustive: a test that is flaky
  roughly 1/3 of the time still clears a 2-run check roughly 4/9 of the time (documented
  limitation, §8).
- The loop stops per cell at 2 consecutive rounds with no new kills (`dry_rounds=2`) or at 4 total
  rounds (`max_rounds=4`), whichever comes first (`crucible.loop.LoopConfig`, `experiments/protocol.json`).

## 8. Limitations

- **Training-data contamination.** All five subjects are public repositories (or, for the local
  subjects, public-facing GitHub projects); the tester and critic models may have seen the exact
  module, or code very like it, during pretraining. This is disclosed, not correctable within this
  design. The mutant-kill metric blunts but does not eliminate the effect: a memorized test suite
  would need to specifically target the *injected* mutant, not just the original code, to count as
  a kill, so contamination inflates plausibility of "looks like a good test" without guaranteeing
  it inflates the kill rate — but the risk is not zero and is named here rather than assumed away.
- **Mutant-environment detection by hostile tests is not closable without sandboxing.** A
  sufficiently adversarial generated test could in principle detect properties of the mutation
  harness itself (timing, file paths, environment markers) rather than the mutant's actual
  behavioral difference, and pass or fail on that basis instead of on the intended semantics. This
  project does not run generated tests inside a syscall sandbox (spec §10, explicitly out of
  scope), so this class of gaming is not mechanically closed — the existing guardrails
  (add-only, pristine-validity, flake check, anti-weakening) reduce but do not eliminate it.
- **2-run flake check.** As in §7, a test flaky roughly 1/3 of the time clears the 2-run check
  roughly 4/9 of the time. A more expensive N-run check was not adopted for this protocol; some
  residual flaky-kill noise in the receipts is expected and is not separately modeled.
- **Single tester model.** The Tester is `claude-sonnet-5` in every arm and every subject; this
  design measures the *Critic's* lineage effect (H2) holding the Tester fixed. It does not measure
  whether a different Tester lineage changes either H1's or H2's result, and no claim is made about
  that.
- **idna's `cli.py` reads stdin in `main()`.** `idna/cli.py`'s `main()` reads `sys.stdin` when
  invoked as a CLI. This does not happen at import time or during mutant generation/collection, so
  it was accepted as a subject module during selection (`experiments/subjects.json` selection_log,
  entry 5) rather than excluded as IO-heavy; it is named here so a reader of the results knows the
  module has a live-input code path that mutmut's static mutation and pytest's collection never
  actually execute.
- **attrition-risk-ml's pinned module differs from its feature-branch version.** The pinned
  `src/train.py` (origin/main, 202 lines) lacks the `CalibratedClassifierCV`/Brier-score
  calibration wrapper present on the project's unmerged `fix/calibration` branch (284 lines) — a
  real content difference, not cosmetic (`experiments/subjects.json` notes). The repin from the
  feature branch to `origin/main` was made because the feature branch has no public ref; this
  protocol scores the `origin/main` version only, and any future re-run against the calibration
  branch would be a different subject-module, not a rerun of this cell.

## 9. Budget

- Every round is metered exactly from the round's `input_tokens`/`output_tokens`
  (`crucible.meter.cost_usd`, `oracle_gate.providers.Usage`), never estimated; an unpriced model
  raises `UnpricedModel` and fails the run closed rather than pricing at a wrong rate
  (`crucible/meter.py`).
- Receipts (`meta.json`, `receipt.jsonl`, `result.json` per run — `crucible.receipts.ReceiptWriter`)
  are committed to `experiments/runs/` **per subject**, as each subject's cells complete — not
  batched to the end of the grid — so a crash loses at most the in-flight round's evidence, never
  an already-completed subject's.
- **`gpt-5.6`'s rate in `crucible.meter.RATES_EXTRA` is a placeholder** (`("gpt-5.6", (1.75, 14.0))`,
  code comment: "placeholder — MUST be verified before first paid GPT run") and **must be verified
  against the live OpenAI pricing page before the first `loop-cross` (H2) call**, with the
  verification date recorded in the `RATES_EXTRA` code comment at that time (plan Task 7 Step 1).
  No `loop-cross` cell runs against an unverified rate.

## 10. Approval

Approved by: Jeff Otterson, ____ (date)
