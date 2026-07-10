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

**Amendment (protocol_version 5 — sandbox stats-failure fails loud instead of recording a
plausible zero; two PAID cells reclassified; a second, distinct scoping bug found and
flagged, NOT fixed by this amendment):**

`crucible.engine.MutmutEngine._zero_test_baseline` (the v4 fix above) has a blind spot: its
own confirmatory check — a bare `pytest -q --ignore=mutants` — runs on the **pristine**
subject tree, never through mutmut's `mutants/` sandbox. A generated test that passes that
pristine check can still crash the instant mutmut wraps the module (a directory `also_copy`
never carried in, or mutmut's own trampoline rejecting a package-qualified import), leaving
every mutant `not checked` for a reason that has nothing to do with legitimate zero
coverage. `_zero_test_baseline` could not tell the two cases apart and silently converted
the crash into a **false all-survived zero** — the exact silent-corruption mechanism named
in this amendment's title.

- **Reproduced for real, in a throwaway `/tmp` clone, no real clone touched.** The
  `attrition-risk-ml` `oneshot` cell's own archived accepted test
  (`experiments/runs/attrition-risk-ml/oneshot-20260710T175155Z/accepted/
  crucible_r0_oneshot_test.py`) was copied into a scratch copy of
  `~/crucible-subjects/attrition-risk-ml` (never the real clone). It passes cleanly against
  the pristine module (`pytest -q`: 18 passed) and passes the `_zero_test_baseline`
  confirmatory check too (`pytest -q --ignore=mutants`: 23 passed, exit 0) — but `python -m
  mutmut run` in that same scratch clone crashes: `AssertionError: Failed trampoline hit.
  Module name starts with `src.`, which is invalid` inside mutmut's own trampoline, ending
  in `failed to collect stats. runner returned 1`. This is byte-for-byte the shape of the
  real recorded run (`experiments/runs/attrition-risk-ml/oneshot-20260710T175155Z/
  result.json`: `baseline_counts` = `{"killed": 0, "survived": 255, ...}`, `status: "ok"`,
  no error ever raised) — confirming the real run's 255-survived-0-killed baseline was this
  exact laundered crash, not a real measurement.
- **Fix, at the engine level.** `crucible.engine.MutmutEngine.measure` now wraps its `run`
  callable in a `_RunTee` that captures the `mutmut run` invocation's stdout+stderr (the one
  subprocess call in `oracle_gate.runner.run_mutation` whose output is otherwise discarded
  after only its exit code is checked). When `undetected()` raises `UnclassifiedStatus`
  (every mutant `not checked`), `_sandbox_stats_failure_tail` scans that captured output for
  `"failed to collect stats. runner returned <N>"` with `N != 5`, or an early `"Stopping
  after <N> failures"` abort — `runner returned 5` (no test files exist anywhere) is the one
  legitimate empty-suite signal, left to `_zero_test_baseline`; any other code or an early
  abort means pytest itself broke or failed *inside* the sandbox, a real crash. A match
  raises `SandboxStatsFailure(RuntimeError)` — checked, and takes priority, BEFORE
  `_zero_test_baseline` ever runs its own (blind) confirmatory check — naming the failing
  tail of `mutmut run`'s output in the message.
- **Fix, in the loop.** `crucible.loop._round`'s post-write `after = env.measure()` call now
  catches `SandboxStatsFailure` separately from the existing `GuardrailViolation` handling:
  the generated test file is removed (`env.remove_test_file`, archived to the run's
  `rejected/` dir when an artifact dir is set, same as any other rejected round), the round
  is recorded `status="rejected"`, `note="sandbox-invalid: " + str(exc)`, and
  `survivors_after` is left equal to `survivors_before` — the round contributes zero kills
  to any metric, exactly like any other rejected round (§6), instead of ever being recorded
  as a real measurement. The **PRE-round baseline** measure (`pre = env.measure()` in
  `crucible.loop._run`, called before any generated test exists) is deliberately left
  unguarded: a `SandboxStatsFailure` there cannot be caused by a generated test and is a
  genuine subject-config error, so it propagates uncaught and crashes the run loud, per this
  protocol's existing stance on hard-stop config errors (§3.2).
- **Two PAID cells reclassified INSTRUMENT-INVALID, not counted data:**
  `attrition-risk-ml` `oneshot` (`oneshot-20260710T175155Z`, $0.123393) and `loop-same`
  (`loop-same-20260710T175320Z`, $0.878028) — both driven by the exact crash reproduced
  above. Both cells are preserved as evidence and will be fresh reruns under `crucible`
  v5 (the rerun itself is out of scope for this amendment — see `DEVIATIONS.md`).
- **`rag-guard`'s two PAID cells (`oneshot-20260710T174312Z`, $0.110742;
  `loop-same-20260710T174420Z`, $0.373071) are ALSO reclassified INSTRUMENT-INVALID, but
  investigation found a DIFFERENT root cause that this amendment's detector does NOT catch.**
  `rag-guard`'s `pytest_args` scope (`protocol.json`: `["tests/test_guard.py"]`) is passed
  verbatim to mutmut's own `PytestRunner._pytest_args_regular_run` as the **sole**
  test-selection argument for its stats-collection pytest invocation
  (`mutmut/__main__.py`) — an include-list, not an additional filter. A freshly generated
  `tests/crucible_*_test.py` file is copied into `mutants/` (confirmed: it is present on
  disk there) but mutmut **never asks pytest to collect it**, so it can never contribute a
  kill, in any round, regardless of what it asserts. This produces no `"failed to collect
  stats"` or `"Stopping after"` marker — mutmut completes normally, with a real,
  internally-consistent killed/survived split — so v5's detector cannot and does not fire
  for it. Confirmed against the recorded receipt
  (`experiments/runs/rag-guard/loop-same-20260710T174420Z/receipt.jsonl`): baseline and all
  3 rounds report the byte-identical `{"killed": 45, "survived": 26}` and `kills: []` every
  round. **Rerunning `rag-guard` under v5 alone will reproduce this identical silent zero —
  a separate scope fix (e.g. widening `pytest_args` to also collect
  `tests/crucible_*_test.py`, or dropping the include-list restriction in favor of another
  fix for the file it exists to exclude, `tests/test_hook.py`) is required first.** Not built
  under this amendment (out of scope; flagged for a future amendment/DEVIATIONS entry before
  any rerun).
- **Open concern, NOT resolved by this amendment: `graph-guard`'s currently-COUNTED cells
  show the identical signature.** `graph-guard` carries the same shape of `pytest_args`
  restriction (`["tests/test_ppr.py"]`) as `rag-guard`. Its counted `oneshot` cell
  (`oneshot-20260710T170024Z`, $0.206295) shows `kills: []` with baseline and round-0 counts
  byte-identical (`{"killed": 58, "survived": 22}`); its counted `loop-same` cell
  (`loop-same-20260710T170726Z`, $0.610452) shows the same at round 0 (`kills: []`,
  identical `{"killed": 58, "survived": 22}`) before its two critic rounds both hit the
  pristine-validity rejection gate. §3.2's v4 amendment stated "graph-guard zeros occurred
  at validity stage pre-measure" for its earlier shakeout cells — that remains true for the
  *rejected* rounds, but it does **not** account for round 0's zero-kills-with-identical-
  counts pattern in either counted cell, which structurally matches the same
  `pytest_args`-exclusion mechanism just confirmed for `rag-guard`, not a genuine "the
  tester found nothing to kill" result. **This protocol's prior determination that
  graph-guard's counted cells are unaffected is therefore NOT verified and must be treated
  as an open question — not a stated fact — until the same reproduction-and-fix discipline
  applied to `attrition-risk-ml` above is applied to `graph-guard`.** No `graph-guard` data
  is reclassified by this amendment (that requires its own verification pass); this is
  logged here so it is not silently trusted in the interim.

v5 approved by Jeff Otterson 2026-07-10 (interactive gate).

**Amendment (protocol_version 6 — include-list `pytest_args` converted to exclude-form;
canary must-kill probe added to `experiments/validate_scopes.py`; graph-guard's v5 open
concern settled INSTRUMENT-INVALID; no paid cell run under this amendment):**

v5 left one confirmed reclassification (`rag-guard`) and one open concern (`graph-guard`)
sharing the same suspected root cause: `mutmut`'s `PytestRunner._pytest_args_regular_run`
(`mutmut/__main__.py`) treats `[tool.mutmut] pytest_add_cli_args_test_selection` — the
config key `protocol.json`'s `pytest_args` writes via `crucible.engine.write_scope` — as
the **sole** positional test-selection argument to its stats-collection pytest invocation
whenever no per-mutant coverage-selected tests apply (`tests=[]`, exactly the case at the
initial stats phase every cell starts from). A scope naming exactly one file
(`["tests/test_guard.py"]`, `["tests/test_ppr.py"]`) is therefore an **include-list**, not
an additional filter: mutmut never asks pytest to collect anything else, so a freshly
written `tests/crucible_*_test.py` file — present on disk, correctly `also_copy`'d in — is
never collected and can never contribute a kill, in any round, no matter what it asserts.
This is verified directly against the installed `mutmut` package source in this repo's own
`.venv` (`_pytest_args_regular_run`, `run_stats`), not inferred from receipt behavior alone.

- **Fix: exclude-form scopes.** `protocol.json`'s `graph-guard` and `rag-guard` entries now
  carry `pytest_args` as `--ignore=` flags instead of bare file paths — mutmut passes these
  straight through as extra pytest CLI args, so pytest's normal recursive discovery under
  the sandbox's `tests/` still runs, minus the named files:
  - `rag-guard`: `["--ignore=tests/test_hook.py"]` (unchanged reason from the v4 amendment:
    `tests/test_hook.py` does `from bin import hook_userpromptsubmit`, a top-level `bin`
    package never in `also_copy`, `ModuleNotFoundError` inside the sandbox).
  - `graph-guard`: `["--ignore=tests/test_sparql_vs_ppr.py", "--ignore=tests/test_eval.py",
    "--ignore=tests/test_real_vault_lift.py"]` — **wider than §3.2's original table**, which
    named only `test_sparql_vs_ppr.py`. Reproducing the exclude-form conversion in a scratch
    clone (never the real clone) found `tests/test_eval.py` and `tests/test_real_vault_lift.py`
    carry the identical `from eval.… import …` top-level-package problem
    (`ModuleNotFoundError: No module named 'eval'`) — invisible under the old include-list
    because mutmut never collected *any* file besides `tests/test_ppr.py`, so these two
    files' own collection errors were silently never exercised either. All three are
    confirmed via `grep -n "^from \|^import " tests/test_*.py | grep -v graph_guard` against
    the real `~/graph-guard` clone: exactly these three files import a top-level package
    outside `also_copy=["graph_guard"]`; every other file's imports (`rdflib`, `owlrl`,
    `hypothesis`, stdlib) are venv-installed third-party packages, not local top-level
    packages, and collect fine.
  - The other three subjects (`attrition-risk-ml`, `packaging`, `idna`) carry no `pytest_args`
    entry at all — confirmed by inspection of `protocol.json`'s `subjects` map — so this
    amendment does not touch them.
  - Verified in throwaway scratch copies of the `rag-guard` and `graph-guard` clones (never
    the real clone): `python -m pytest -q` and `python -m pytest -q --ignore=…` both pass
    cleanly at the repo-root level (52/49 passed, 150/142 passed respectively) — a sanity
    check, not the definitive proof, since the `ModuleNotFoundError` only manifests **inside**
    mutmut's `mutants/` sandbox where `bin`/`eval` are absent (they're never `also_copy`'d);
    the canary probe below is what actually exercises the sandbox.
- **Fix: canary must-kill probe, `experiments/validate_scopes.py`.** The pre-existing
  count-match check proves the mutant *denominator* is right but never proves mutmut's stats
  phase actually collects a freshly-written test file — exactly the gap above. Each subject
  in `protocol.json` now carries a `canary` field: a small, hand-written pytest file body
  asserting one fact read directly from the pinned module's source (never guessed), chosen
  so mutating that fact breaks it:
  - `attrition-risk-ml`: calls `train._candidates()` (real function coverage, not a bare
    constant read — see below) and asserts it returns exactly the three named model keys.
  - `graph-guard`: `personalized_pagerank` on a hand-computed 2-node symmetric graph,
    asserted via `pytest.approx` against the converged score pair.
  - `rag-guard`: `should_refuse([{"score": 0.5}])` is `False` under the module's own default
    `min_score=0.05`.
  - `packaging`: a hand-built minimal ELF32-LSB header (`struct.pack`, `e_machine=62`) parsed
    by `ELFFile`, asserted against the known `EMachine.X8664` enum value.
  - `idna`: `_looks_like_alabel` on a known ACE-prefixed label (`True`) and a known plain
    label (`False`).

  The probe (`run_canary_probe`) resets the clone, writes the canary, **confirms it passes
  pristine on its own first** ("a failing canary is your bug, not the subject's" — never
  relied on unverified), then runs `mutmut run` for real and compares the measured killed
  count against the count-match check's own baseline (measured moments earlier, before the
  canary existed). Verdict is **KILLS** iff the killed count strictly increases — not a raw
  `killed >= 1` threshold, because an already-covered subject's pre-existing suite can supply
  a large nonzero killed count with or without the canary ever running (`rag-guard`'s
  pre-existing `test_guard.py` alone kills 45+; a naive `>=1` check would show KILLS under
  the broken OLD scope too, since that pre-existing suite is still the sole thing collected).
  The clone is always reset in a `finally`, success or failure.
- **`attrition-risk-ml`'s canary needed a second, independent workaround, unrelated to the
  include/exclude scope issue.** A first canary attempt (`from src.train import RANDOM_STATE`)
  produced neither a crash nor a kill: `mutmut run` printed "Stopping early, because we could
  not find any test case for any mutant" and every mutant stayed `not checked`. Root cause,
  confirmed by reading `mutmut/__main__.py` directly: `record_trampoline_hit` hard-asserts
  `not name.startswith("src.")` — mutmut's own per-call coverage instrumentation (the
  "trampoline") refuses any hit whose dotted module name starts with `src.`, and only fires
  for **function calls**, never for a bare module-level constant read, so a canary that never
  calls a real function in `train.py` registers zero coverage and mutmut can't map any mutant
  to it at all. This is the same crash class the v5 amendment already reproduced for the
  `attrition-risk-ml` H1 cells (`AssertionError: Failed trampoline hit. Module name starts
  with 'src.', which is invalid`) — calling `_candidates()` via `from src.train import
  _candidates` reproduces it identically in a scratch clone. Fix, canary-side only (no engine
  or protocol change — this is a property of how the canary imports the module, not the scope):
  `mutmut`'s own `setup_source_paths()` (`mutmut/__main__.py`) adds `mutants/src` to `sys.path`
  specifically so tests can import the bare module name (`train`, not `src.train`) and avoid
  this exact collision; the canary does the same by hand
  (`sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))` before `from train
  import _candidates`), which resolves identically pristine (no `mutants/` dir; the manual
  `sys.path` entry does the same job) and inside the sandbox. Verified: 0k → 9k (delta +9).
  **This is flagged, not fixed, as a standing limitation for any future real generated test
  against `attrition-risk-ml`:** a tester/critic model naturally writes `from src.train import
  …` (the same convention the subject's own `tests/test_data.py` uses for `src.data`, and the
  only way to import the module that VS Code / a human would write given the repo's actual
  package layout), and doing so crashes mutmut's trampoline the instant it calls any real
  function in `train.py` — a genuine `mutmut`-library limitation with `src`-named packages,
  not something this amendment's scope-fix or the v5 `SandboxStatsFailure` detector addresses.
  Out of scope for this amendment; noted here so it is not lost.
- **Validation: all 5 subjects, real local `mutmut run`s, $0, no model ever called
  (`FakeProvider`, unconstructed for calls).** `experiments/validate_scopes.py` (extended,
  not rewritten) run against the real pinned clones:

  | Subject | Count-match | Canary (baseline → post-canary killed) |
  |---|---|---|
  | attrition-risk-ml | MATCH (255m 0k 255s) | KILLS (0k → 9k) |
  | graph-guard | MATCH (80m 58k 22s) | KILLS (58k → 63k) |
  | rag-guard | MATCH, widened-scope note (71m 46k 25s vs. smoke 45k/26s) | KILLS (46k → 47k) |
  | packaging | MATCH, stripped-suite 0k by design (69m 0k 69s) | KILLS (0k → 24k) |
  | idna | MATCH, stripped-suite 0k by design (187m 0k 187s) | KILLS (0k → 7k) |

  `rag-guard`'s measured split (46k/25s) differs from its recorded smoke (45k/26s) by exactly
  +1 killed / -1 survived — the expected, correct signature of the exclude-form widening (one
  additional pre-existing test file beyond `test_guard.py` now legitimately gets collected and
  kills one more mutant than the old include-list ever let run); `validate_scopes.py`'s
  `validate_subject` now treats a strictly-more-kills, never-fewer split as a documented pass
  for this reason, distinct from the stripped-suite 0-kill case. A split showing *fewer* kills
  than smoke still fails loud (unchanged).
- **graph-guard's v5 open concern is SETTLED: its counted `oneshot`/`loop-same` H1 cells are
  INSTRUMENT-INVALID, not merely suspected.** Direct old-vs-new comparison, both runs against
  the same real pinned clone, same canary, same mutant population (80 mutants):
  - **OLD** scope (`pytest_args: ["tests/test_ppr.py"]`, byte-identical to the config the two
    counted cells actually ran under): canary written, confirmed pristine-passing, `mutmut run`
    measures 58 killed both before and after the canary exists — **NO-KILLS, delta +0**. The
    canary file is present on disk in the sandbox and never touched.
  - **NEW** scope (this amendment's exclude-form): same canary, same clone, same mutant
    population: 58 killed before, 63 killed after — **KILLS, delta +5**.

  This directly reproduces, for graph-guard, the exact mechanism `rag-guard` was reclassified
  for under v5: a structurally guaranteed zero contribution from any newly generated test file,
  regardless of what it asserts, entirely explained by the config, with the config change alone
  flipping the outcome. **`graph-guard`'s two counted H1 cells
  (`experiments/runs/graph-guard/oneshot-20260710T170024Z/`, $0.206295, and
  `experiments/runs/graph-guard/loop-same-20260710T170726Z/`, $0.610452 — $0.816747 total) are
  therefore reclassified INSTRUMENT-INVALID, not counted data**, joining `rag-guard`'s v5
  reclassification. Both cells and their receipts are preserved as evidence
  (`experiments/DEVIATIONS.md`); fresh reruns under v6 are a controller action, out of scope
  for this amendment (no paid cell runs under this amendment — every measurement above uses
  `FakeProvider`, never constructed to call, per `validate_scopes.py`'s own $0 invariant).

v6 approved by Jeff Otterson 2026-07-10 (interactive gate) — continuation of the same
instrument-repair approval standing established for v5.

**Amendment (protocol_version 7 — src-layout import shim + per-subject import hint,
instrument-repair continuation; no paid cell run under this amendment):**

v6's canary section flagged, but did not fix, a standing `mutmut`-library limitation:
`attrition-risk-ml`'s `src/train.py` is only importable, from `mutmut`'s own trampoline's
perspective, as the bare module name `train` — a dotted `src.train` import crashes
`record_trampoline_hit` (`mutmut/__main__.py`) the instant any real function in the module
is called inside the `mutants/` sandbox. `src.train` is nonetheless the natural, arguably
only-obvious import a model or a human would write given the repo's real package layout
(the subject's own `tests/test_data.py` already imports `src.data` this way). Left
unaddressed, every real generated Tester/Critic test against `attrition-risk-ml` would hit
`SandboxStatsFailure` (v5) on its first round, every round, for a reason that has nothing to
do with test quality.

- **Fix: per-subject `extra_files` — a clone-root import shim, committed with the scope.**
  `experiments/protocol.json` subjects may now carry an optional `extra_files` map
  (filename → file content) alongside the existing `module`/`also_copy`/`pytest_args`/
  `canary` keys. `attrition-risk-ml`'s entry carries one: `conftest.py` inserting
  `src/` onto `sys.path` (`sys.path.insert(0, str(pathlib.Path(__file__).parent /
  "src"))`) — the same mechanism `mutmut`'s own `setup_source_paths()` uses internally,
  applied at the subject-clone root so it resolves identically pristine and inside the
  sandbox. `SubjectEnv.preflight` (`src/crucible/env.py`) writes each `extra_files` entry
  into the clone root — only when its content actually differs from what's already there,
  so a repeat preflight against an already-shimmed clone is a true no-op — **before** the
  `[tool.mutmut]` scope write, so both land in the **same** commit; the commit message
  becomes `"crucible: scope mutmut to <module> (+shims)"` when `extra_files` is present
  (unchanged, no suffix, for every subject without it). A receipt's `head_sha` therefore
  covers the shim, not just the scope.
- **Fix: per-subject `import_hint` — one mandatory prompt rule, in the hashed user text.**
  Subjects may also carry an optional `import_hint` string. `crucible.roles
  .build_tester_prompt`/`build_critic_prompt` gained an `import_hint` parameter; when set,
  it is appended as one more "mandatory rule" line in the **user** message, never the
  shared **system** template — hash discipline: the hint varies per subject (it names that
  subject's own module-import convention), so it must live in the part of the prompt that
  is hashed per-call, not the part shared and hashed identically across every subject.
  `SubjectEnv.call_tester`/`call_critic` thread `scope.get("import_hint")` through
  automatically; omitting the field (or passing `None`) reproduces the prompt v6 hash
  exactly (verified: `tests/test_roles.py
  ::test_tester_prompt_hash_identical_for_omitted_and_explicit_none_hint`).
  `attrition-risk-ml`'s hint: "Import the module under test as `import train` /
  `from train import ...` (the src/ directory is on sys.path via conftest; do NOT import
  src.train)." No other subject carries `import_hint` or `extra_files` — none of the
  other four hit this failure class.
- **`load_protocol` validates both new fields when present, tolerates their absence.**
  `crucible.experiment.load_protocol` now checks, per subject: `extra_files`, if present,
  must be a dict of `str -> str`; `import_hint`, if present, must be a `str`. Neither field
  is required — a v6-shaped subject entry with neither key still loads unchanged
  (`tests/test_experiment.py::test_load_protocol_v7_subject_without_new_fields_still_works`).
- **`attrition-risk-ml`'s canary rewritten to the same import style the hint mandates.**
  The v6 canary's manual `sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
  "src"))` (duplicated by hand in the test file itself) is dropped; the v7 canary now
  reads simply `from train import _candidates`, relying on the same `conftest.py` shim
  `extra_files` writes into every real generated test's clone. This is not a cosmetic
  change: it proves the shim actually does the job the manual hack used to do, under the
  identical mechanism a real Tester/Critic-generated file will use.
- **Verified: `experiments/validate_scopes.py`, all 5 subjects, real local `mutmut run`s,
  $0, no model ever called.** Count-match and canary-must-kill both re-run clean under the
  v7 protocol (which now writes the shim as part of every `attrition-risk-ml` preflight):

  | Subject | Count-match | Canary (baseline → post-canary killed) |
  |---|---|---|
  | attrition-risk-ml | MATCH (255m 0k 255s) | KILLS (0k → 9k) |
  | graph-guard | MATCH (80m 58k 22s) | KILLS (58k → 63k) |
  | rag-guard | MATCH, widened-scope note (71m 46k 25s vs. smoke 45k/26s) | KILLS (46k → 47k) |
  | packaging | MATCH, stripped-suite 0k by design (69m 0k 69s) | KILLS (0k → 24k) |
  | idna | MATCH, stripped-suite 0k by design (187m 0k 187s) | KILLS (0k → 7k) |

  Identical figures to the v6 table — this amendment changes *how* the canary imports
  `train.py` (and, going forward, how a real generated test will), not the measured
  scope or kill counts for any subject. `~/crucible-subjects/attrition-risk-ml`'s HEAD
  now carries `conftest.py` committed alongside `[tool.mutmut]` (commit `aa4bae1
  crucible: scope mutmut to src/train.py (+shims)`), confirmed via `git show
  HEAD:conftest.py` after the validator's own reset-to-HEAD.
- **Suites green.** `tests/` fast suite (excludes `slow`/`integration`): 171 passed. `-m
  slow` suite (real mutmut, seconds on the tiny fixture): 2 passed.

This closes the standing limitation the v6 amendment's canary section named but did not
fix ("flagged, not fixed, as a standing limitation for any future real generated test
against `attrition-risk-ml`") — the instrument-repair work this protocol's amendment
sequence (v2 through v7) has been performing is now complete for all five subjects: every
subject's count-match and canary-must-kill checks pass, and the one subject with a
library-level import-crash limitation now carries a shim + hint pair that fixes it before
any real Tester/Critic call, rather than only in the free validator's own canary.

v7 approved by Jeff Otterson 2026-07-10 (interactive gate) — continuation of the same
instrument-repair approval standing established for v5 and v6.

**Amendment (protocol_version 8 — H2 critic pinned to a real variant id, rate verified live;
PRE-DATA, zero loop-cross cells have run):** OpenAI's GPT-5.6 ships as three variants (Sol,
Terra, Luna); the bare id `gpt-5.6` this protocol and `crucible.meter.RATES_EXTRA` carried
since §1/§9 does not exist and would never have resolved against a real API. `experiments
/protocol.json`'s `loop-cross` critic is now pinned to `gpt-5.6-terra`, and `RATES_EXTRA`
carries its verified per-1M-token rate, $2.50 in / $15 out (verified 2026-07-10 against the
openai.com announcement plus two independents) — the old `("gpt-5.6", (1.75, 14.0))`
placeholder is removed outright, so the never-existed bare id now fails closed
(`UnpricedModel`) rather than silently pricing at a wrong rate. Terra was chosen over Sol
(flagship, $5/$30) because it is the tier- and price-matched sibling to the same-lineage
Tester/loop-same Critic, `claude-sonnet-5` ($3/$15) — pinning the price/capability tier this
way isolates the lineage variable H2 measures; Sol would confound lineage with capability
tier, weakening the comparison. This is pre-data for H2 (zero `loop-cross` cells have run
under any protocol version); approved under Jeff's standing GPT-arm gate (credentials +
verified rate) — credential ping receipt: 16 in / 4 out tokens, 2026-07-10, confirming both
auth and live credits against `gpt-5.6-terra` before this pin.

v8 approved by Jeff Otterson 2026-07-10 (interactive gate) — closes §9's "MUST be verified
before the first `loop-cross` (H2) call" requirement.

**Amendment (protocol_version 9 — Anthropic output cap silently truncated same-lineage critic
replies, laundered into misleading rejection notes; four counted cells reclassified
INSTRUMENT-INVALID; found by a final adversarial review of the completed analysis, after all
15 counted cells had already run):**

`src/crucible/providers_ext.py`'s `LongAnthropicProvider` set `max_tokens=16000` on every
Anthropic call (the Tester in every arm; the Critic in `loop-same`) and nowhere in
`crucible.env.SubjectEnv._call` or `crucible.loop._round` was a reply's `usage.output_tokens`
ever compared against that cap, and `stop_reason`/truncation was never inspected at all. A
reply that hit the wall came back as ordinary, well-formed-looking text cut off mid-JSON or
mid-test-file, indistinguishable at the call site from a complete reply — it was handed
straight to guardrail validation, which then failed it for an unrelated-sounding reason (an
unterminated fenced code block reads as "expected exactly one fenced python block, found 0";
a syntactically broken test file reads as "invalid: fails on pristine code"), and the round was
recorded rejected under that misleading note with no trace anywhere in the receipt that the
reply had in fact been silently cut off billed and unusable, not a bad test.

**Mechanism of the asymmetry.** The Tester is `claude-sonnet-5` (`anthropic`) in every arm and
every subject (§2); the `loop-same` Critic is also `anthropic`/`claude-sonnet-5` — the
**same-lineage** configuration H2 is built to isolate. Claude Sonnet 5 writes long: critic
replies that walk through each survivor's diff and reasoning routinely approached or exceeded
the old 16000-token ceiling. The `loop-cross` Critic, `gpt-5.6-terra` (`openai`), writes terse
by comparison and never hit any cap in any counted cell (verified below). The result is a
structural, lineage-correlated failure mode entirely orthogonal to either critic's actual test-
writing quality: the same-lineage arm this protocol measures against a cross-lineage arm was the
*only* one mechanically capable of losing whole rounds to silent truncation, which would bias
any H2 comparison toward making `loop-same` look worse than its real output, for a reason having
nothing to do with lineage-driven test quality.

**Detection asymmetry — a residual limitation, not closed by this fix.** `OpenAIProvider`
(`oracle_gate.providers`, used for the `loop-cross` Critic) sends no `max_tokens` in its request
body at all and carries no `output_cap` class attribute; `SubjectEnv._call`'s truncation check
is `cap = getattr(provider, "output_cap", None); if cap is not None and usage.output_tokens >=
cap: raise TruncatedOutput(...)` — a provider with no `output_cap` is never checked, by
construction. If GPT-5.6-terra ever truncates a reply against whatever ceiling OpenAI's API
enforces server-side, this protocol's instrumentation would launder it exactly the way the
Anthropic case above was laundered, with no mechanical detection and no receipt trace. This
amendment does not close that gap — it is named here as a standing, asymmetric blind spot: only
providers that declare a mechanical `output_cap` are checked for truncation at all.

**Verified receipt evidence (this protocol's own re-derivation, not the originating review's
count).** Reading every round of every one of the 15 cells in the (then-current)
`experiments/counted.json` directly from `receipt.jsonl`: **8 rounds carry `status="rejected"`
across counted cells, of which 7 billed `usage_out` exactly `16000`** — the earlier review that
flagged this defect reported "6 of 7"; recomputing independently from the receipts finds an
eighth rejected round it missed (`attrition-risk-ml` `loop-same`, round 1, critic, note
"expected exactly one fenced python block, found 0", `usage_out=16000` — a second truncated
critic round in the same cell as the round-2 rejection already suspected). The 7 confirmed
truncations:

| Subject | Arm | Round | Role | usage_out | Rejection note (as recorded) |
|---|---|---:|---|---:|---|
| graph-guard | loop-same | 1 | critic | 16000 | invalid: fails on pristine code |
| graph-guard | loop-same | 2 | critic | 16000 | invalid: fails on pristine code |
| graph-guard | loop-cross | 0 | tester | 16000 | invalid: fails on pristine code |
| packaging | loop-same | 1 | critic | 16000 | invalid: fails on pristine code |
| packaging | loop-same | 2 | critic | 16000 | invalid: fails on pristine code |
| attrition-risk-ml | loop-same | 1 | critic | 16000 | expected exactly one fenced python block, found 0 |
| attrition-risk-ml | loop-same | 2 | critic | 16000 | invalid: fails on pristine code |

The 8th rejected round, `attrition-risk-ml` `loop-cross` round 4 (critic, `usage_out=1433`,
"invalid: every generated test failed on pristine code (dropped
['test_run_writes_metrics_to_lowercase_metrics_json'], nothing left to salvage)"), is a genuine
content-based rejection, not truncation (`usage_out` is nowhere near the cap) — that cell is
unaffected by this defect and is not reclassified. `graph-guard`'s `loop-cross` cell's death is
confirmed to be the identical mechanism at the Tester role: round 0 (the only round `loop-cross`
ever reached for `graph-guard`, since a rejected Tester round ends the cell) hit the cap and was
laundered into "invalid: fails on pristine code," never recorded as a truncation. No `loop-cross`
critic round in any counted cell ever billed `usage_out` at or near 16000 (observed range across
all `loop-cross` critic rounds: 314-9614, `rag-guard`/`idna`/`packaging`/`attrition-risk-ml`
combined) — confirming the terse-vs-verbose asymmetry described above directly from the data, not
merely asserted from each model's general style.

**Fix (already committed, code-reviewed and reviewer-approved before this amendment, commit
`68968c1`):** `LongAnthropicProvider.output_cap` raised from the old hardcoded 16000 to 32000,
now the single source of truth both `_body` (the actual request) and `env._call` (the mechanical
check) read from. `env._call` compares every reply's `usage.output_tokens` against
`getattr(provider, "output_cap", None)` and raises `TruncatedOutput` — never retried (retrying a
capped call would bill and likely truncate again) — carrying the billed usage, model, and
prompt hash. `crucible.loop._round` catches `TruncatedOutput` and records the round honestly:
`status="rejected"`, `note` exactly `"truncated: output hit max_tokens cap (output_tokens=<N> >=
max_tokens=<CAP>)"`, the round's real billed cost entered in the receipt (the tokens were spent
and must be metered, per §9), zero kills credited, and the raw truncated reply archived to the
run's `rejected/` directory via the new `env.archive_rejected_text` (evidence preserved, never
discarded, same posture as every other rejected-round artifact under §6). A truncation at round
0 of any arm still fails that cell's verdict loud through the existing verdict path — it is a
missing cell, not a silently-recovered one.

**Consequence: four counted cells reclassified INSTRUMENT-INVALID, preserved as evidence, fresh
reruns under this amendment to follow (`experiments/DEVIATIONS.md`):**

- `graph-guard` `loop-same-20260710T191858Z` ($0.606144) — rounds 1 and 2 (both critic) truncated.
- `graph-guard` `loop-cross-20260710T194101Z` ($0.243735) — round 0 (tester) truncated, killing
  the whole cell.
- `packaging` `loop-same-20260710T181157Z` ($0.691623) — rounds 1 and 2 (both critic) truncated.
- `attrition-risk-ml` `loop-same-20260710T193123Z` ($0.809325) — rounds 1 and 2 (both critic)
  truncated.

**The remaining 11 counted cells stand — verified, not assumed.** Every other counted cell's
accepted rounds were checked directly against the receipts: no accepted (`status` other than
`"rejected"`/`"aborted"`) round in any counted cell anywhere billed `usage_out` at or equal to
16000 — the highest accepted-round output among all 15 cells is `idna` `loop-same` round 0
(`usage_out=14623`, a near-miss, still `status="ok"`). Every counted cell's `oneshot` arm (the
only arm with no Critic round at all) is unaffected in every subject. `rag-guard` and `idna`'s
`loop-same`/`loop-cross` cells are unaffected — no rejected round appears in either subject's
receipts at all.

**Why this biases H1 conservative, not inflated.** Every truncation-caused rejection above
occurred in a `loop-same` critic round or a `loop-cross` tester round — never in `oneshot` (no
critic round exists to truncate) and never crediting a phantom kill (a rejected round always
credits zero kills, `survivors_after = survivors_before`, per §6). The practical effect of this
defect, wherever it hit, was to silently *remove* critic rounds `loop-same` should have gotten
to run — reducing, never inflating, the kills `loop-same` could show against `oneshot`. If H1's
pooled result favors `loop-same` despite this defect suppressing some of its own rounds, the true
effect (measured under the v9 fix, after the four cells above are rerun) can only be as large or
larger, never smaller, than what the defect-affected data showed — the defect works against H1's
own hypothesis, not for it.

v9 approved by Jeff Otterson 2026-07-10 (interactive gate).

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
