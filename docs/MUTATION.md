# Mutation-Survivor Triage

## Post-Experiment-B-harness re-run (2026-07-13, feat/experiment-b) — CANONICAL

The PROTOCOL-B seeded-continuation code (`loop.seeded_run`, `loop._critic_phase`,
`ReproductionMismatch`) grew `loop.py`'s share of the population; totals moved
982 -> 1130 (1148 before a cleanup, see below).

| Run | Mutants | Killed | Survived | Untriaged | Overall |
|-----|---------|--------|----------|-----------|---------|
| First run with seeded_run in scope | 1148 | 1092 | 56 | 50 | 95.1% |
| **+ killer tests & no-op-arg cleanup (canonical)** | **1130** | **1125** | **5** | **0** | **99.6%** |

The 50 untriaged survivors were dispatched three ways, in priority order:

- **Killed (~33):** the same class as the score.py episode below — gate MESSAGES
  and receipt FIELDS nothing asserted exactly. `tests/test_loop.py` now pins
  every `ReproductionMismatch` message with full-string equality
  (`test_seeded_gate_messages_are_exact`, `test_resurrection_message_is_exact`)
  and every round-0 receipt field (`test_seeded_round0_record_fields_are_exact`,
  the capturing-env passthrough test, the provenance-defaults test).
- **Deleted (13, better than documenting):** every pre-append `raise` in
  `seeded_run` passed `rounds=rounds` while `rounds` was still the empty list —
  a no-op argument whose only effect was breeding equivalent mutants
  (`rounds=None` / argument dropped). The argument was removed at those six call
  sites (the constructor default is the same empty list), so the mutants ceased
  to exist instead of joining the exemption ledger. Only the resurrection raise,
  where billed rounds genuinely exist, still passes `rounds=`.
- **Excluded with cause (1 test file):** `tests/test_experiment_b.py` reads the
  frozen `experiments/protocol-b.json` from disk, which is outside
  `source_paths`/`also_copy` and therefore absent from mutmut's sandbox — the
  same documented class as `tests/test_analyze.py` (see `pyproject.toml`). Its
  loop.py usage is monkeypatched; every seeded_run mutation-killer lives in
  `tests/test_loop.py`, which stays selected.

**The 5 remaining survivors are all previously documented below** (zero
untriaged, no bare exclusions). `scope.x_detect__mutmut_19`, the documented
environment-limited equivalent, was killed in this local macOS run — its
disposition ("survives case-insensitive filesystems, killed on Linux CI")
already covers both outcomes.

---

## Post-`score` re-run (2026-07-13) — superseded by the run above

Adding `crucible score` + the GitHub Action grew the scope from 7 modules to 8
(`+score.py`) and the mutant population 913 -> 982.

The Action, run against crucible's own code on the very PR that introduced it,
immediately found **4 survivors in `score.py`** and **7 previously-undocumented
survivors in `scope.py`**. All 11 are now killed. None were equivalent.

| Run | Mutants | Killed | Survived | No-cov | Overall |
|-----|---------|--------|----------|--------|---------|
| First run with score.py in scope | 982 | 965 | 17 | 0 | 98.3% |
| + score.py killing tests | 982 | 969 | 13 | 0 | 98.7% |
| **+ scope.py survivor triage (canonical)** | **982** | **976** | **6** | **0** | **99.4%** |

**What the 11 killed survivors were, and why they lived.** Every one was a
string-literal mutant inside a **refusal message** that no test asserted:

- `score.x_mutation_score__mutmut_6/7/8` — the `EmptyMutantSet` message.
- `score.x_shock_line__mutmut_7` — the result sentence.
- `scope.x_apply__mutmut_10..14` (5) — the conftest-collision guidance.
- `scope.x_canary_probe__mutmut_52/53` (2) — the no-public-API refusal.

The tests asserted *fragments* of each message (`match="conftest.py"`,
`startswith(...)`, a bare `pytest.raises`) rather than the message. **A refusal
message is the entire product on those paths** — it is all the user gets when
crucible declines to run — so leaving it unasserted let the instructions rot into
nonsense undetected.

**The trap worth recording.** `pytest.raises(match=...)` does a regex **search**,
not a full match. The mutant that corrupted a message to `"XXno mutants
generated; nothing to scoreXX"` therefore **survived an unanchored `match=`** —
the garbage still *contains* the expected text. The same hole defeats a
substring assertion (`expected in actual`). These are now pinned by **exact
equality**, or with an anchored `^...$` pattern.

**The 6 remaining survivors are exactly the 6 already documented below** (see the
Task-14b section). Zero untriaged survivors; no bare exclusions:

1. `guardrails.x_extract_test_file__mutmut_4` — equivalent, Jeff-approved.
2. `report.x_mcnemar_exact__mutmut_4` — equivalent, Jeff-approved.
3. `guardrails.x__parse_failed_test_names__mutmut_3` — documented.
4. `scope.x_canary_probe__mutmut_125` — documented (the `waived=False` default;
   numbered `__mutmut_120` in the previous pass — mutant indices shift when the
   file changes, the disposition does not).
5. `scope.x_detect__mutmut_19` — environment-limited equivalent (`"tests"` ->
   `"TESTS"`; survives on a case-insensitive filesystem, and **is killed on
   Linux CI** — which the 2026-07-13 CI run confirms).
6. `lean.x__build_argv__mutmut_3` — documented.

---

## Post-fix-wave re-run (Task 14b, 2026-07-10)

The final-review fix wave (pristine baseline, per-round receipt streaming,
preflight, integrity attestation, abort survivor-context) added new code to
`loop.py`, growing the mutant population 375 -> 383.

| | mutants | killed | survived | never reached | raw score |
|---|---|---|---|---|---|
| Task 14a final | 375 | 373 | 2 | 0 | 99.5% |
| Post-fix-wave, before triage | 383 | 377 | 6 | 0 | 98.4% |
| **Post-fix-wave, after triage** | **383** | **381** | **2** | **0** | **99.5%** |

The 4 new survivors were all in `loop.py`'s new denominator plumbing — the
`all_mutants`/`counts` fields set on RoundRecord and the `baseline_counts`
argument to LoopResult — set but never asserted. One targeted test
(`test_round_and_baseline_record_the_full_denominator` in `tests/test_loop.py`,
plus giving the FakeEnv `outcome()` helper a non-empty counts dict so a dropped
`baseline_counts=` argument is distinguishable from the dataclass default)
killed all 4. Verified by a full re-run: `mutmut results` lists exactly the two
Task 14a equivalent mutants below and nothing else. No untriaged survivors.

The 2 remaining survivors are the same two analytically-verified equivalent
mutants documented in the Task 14a section (`x_extract_test_file__mutmut_4`,
`x_mcnemar_exact__mutmut_4`) — dispositions unchanged.

---

# Task 14a triage (historical)

**Date:** 2026-07-10
**Scope:** dogfood run over the five pure modules under `[tool.mutmut] source_paths`
in `pyproject.toml` — `src/crucible/{loop,guardrails,report,meter,roles}.py`.
**Tooling:** `mutmut` (`.venv/bin/python -m mutmut run` / `results` / `show <id>`),
same config as Task 13's dogfood. No source files were changed — only tests.

## Scores

| | mutants | killed | survived | never reached | raw score | covered-code score |
|---|---|---|---|---|---|---|
| **Before** (Task 13 dogfood) | 375 | 313 | 62 | 0 | 83.5% | 83.5% |
| **After** (this pass) | 375 | 373 | 2 | 0 | 99.5% | 99.5% |

Raw and covered-code scores are identical in both rows because `never reached` is 0
throughout — every mutant sits on code some test exercises; the gap is entirely
missing *assertions*, not missing *coverage*.

## Per-module survivor counts (before -> after)

| module | survivors before | survivors after |
|---|---|---|
| loop.py | 23 | 0 |
| guardrails.py | 11 | 1 |
| report.py | 18 | 1 |
| meter.py | 3 | 0 |
| roles.py | 7 | 0 |
| **total** | **62** | **2** |

## Tests added

25 new test functions across the five existing test files (net: 60 -> 85 passing
under `-m "not slow"`), plus one `FakeEnv` upgrade in `tests/test_loop.py` (call-order
tracking + per-call failure injection) needed to distinguish tester-vs-critic model
calls and mid-loop abort timing. No new test files; no source files touched.

- `tests/test_loop.py`: 5 new tests (round/role/survivors_before bookkeeping,
  tester-vs-critic call routing, critic-round abort status/cost, dry-counter reset
  on a kill round, final-line "clean" verdict at budget exhaustion, `test_file` path
  recorded on a successful round)
- `tests/test_guardrails.py`: 8 new tests (exact no-assert message, strip-cutset is
  `"\n"` only, `-2000:` tail slicing on both the invalid and flaky messages,
  add-only empty/None status, blank-line-skip-not-loop-stop, allowed-file
  doesn't short-circuit, `validate_new_tests` call-argument scoping)
- `tests/test_report.py`: 5 new tests (p-value capped at 1.0, `paired_kills` uses
  union not intersection of baselines, `_killed` tolerates a missing `"kills"` key,
  full-shape `summarize()` dict equality, incomplete-run defaults)
- `tests/test_meter.py`: 3 new tests (`UnpricedModel` message names the model,
  empty/None model falls back to `""` not a placeholder key, cost divisor is
  exactly 1,000,000)
- `tests/test_roles.py`: 6 new tests (template path segments via a fake
  `resources.files`, tester/critic template selection, critic-diff join separator,
  NUL-separator hash formula, system/user preserved verbatim)

All five test files pass individually on pristine code; the full fast suite
(`.venv/bin/python -m pytest -q -m "not slow"`) is green: **85 passed, 2 deselected,
0 warnings**.

## Remaining survivors — disposition

Both remaining survivors were verified analytically (not merely "no test found
yet") to be **equivalent mutants**: for every input, the mutated code produces
identical externally observable output to the original. Per the task's rule,
these are documented here with a reason rather than added as exemption entries
(exemptions require the repo owner's named sign-off).

| mutant id | diff summary | class | reason |
|---|---|---|---|
| `crucible.guardrails.x_extract_test_file__mutmut_4` | `model_output or ""` -> `model_output or "XXXX"` (the empty-input fallback string) | equivalent | The fallback only fires when `model_output` is `None`/`""` (both falsy). `_PY_BLOCK` requires a literal ```` ```python\n...``` ```` fence; `"XXXX"` contains no such fence, so `_PY_BLOCK.findall("XXXX")` is `[]`, exactly like `findall("")`. Both paths yield zero blocks and raise the same `GuardrailViolation`. Verified this isn't a filesystem/regex quirk: the only way to make `"XXXX"` behave differently would be for `"xxxx"` to coincidentally match the fence regex, which it cannot (the regex requires backticks). Genuinely unreachable difference, not just untested. |
| `crucible.report.x_mcnemar_exact__mutmut_4` | `if n == 0: return 1.0` -> `if n == 1:` (the short-circuit's guard condition) | equivalent | Worked the algebra by hand for both n values the branch can ever fire on. `n=0` only occurs at `b=c=0`: original short-circuits to `1.0`; the mutant instead falls through to the formula, which evaluates to `comb(0,0)/2**0 = 1.0` — same result. `n=1` only occurs at `(b,c) ∈ {(1,0),(0,1)}`: the mutant short-circuits to `1.0`; original falls through to the formula, `k=0`, `tail = comb(1,0)/2**1 = 0.5`, `min(1.0, 2*0.5) = 1.0` — same result again. The short-circuit and the general formula agree exactly at both n=0 and n=1, so swapping which one triggers the early return changes nothing observable for any (b,c). (Also added `test_mcnemar_exact_p_value_is_capped_at_one` — `mcnemar_exact(1, 1) == 1.0` — which *does* kill a neighboring cap-related mutant, `x_mcnemar_exact__mutmut_27` (`min(1.0, ...)` -> `min(2.0, ...)`); that one is confirmed killed and does not appear in the survivor list above.) |

No survivor was silently dropped and no source bug was found in either of these two
functions — both are working as designed; the mutation happens to land on a spot
where two code paths are provably equivalent for this domain.

## Suspected source bugs

None found. All 62 original survivors were either genuine test gaps (60, now
killed) or provably equivalent mutations (2, documented above) — no case where
"the mutation is equivalent because the original code is wrong."

## Verification

- `.venv/bin/python -m pytest -q -m "not slow"` -> `85 passed, 2 deselected` (0 warnings)
- `.venv/bin/python -m mutmut run` (final pass) -> `375 mutants: 373 killed, 2 survived, 0 never reached`
- `.venv/bin/python -m mutmut results` (final) -> only the two ids above listed as `survived`

---

# Exemption sign-off (2026-07-11)

Both analytically-verified equivalent mutants documented in the Task 14a triage above —
`crucible.guardrails.x_extract_test_file__mutmut_4` and
`crucible.report.x_mcnemar_exact__mutmut_4` — are **approved as exemptions by Jeff
Otterson, 2026-07-11** (interactive gate; approval given after the experiment merged to
main at `687637e`). This is the repo owner's named sign-off the triage rule required;
the analytical dispositions are unchanged. A future mutation run listing exactly these
two ids as survivors is at the documented 99.5% score with zero untriaged survivors.

## 2026-07-12 — public-flip pass: scope.py + lean.py enter the gate; 3a-era drift repaid

Scope grew from 5 modules to 7 (`+scope.py`, `+lean.py` — lean via a behavior-preserving
delegate refactor, because mutmut 3.6 generates ZERO mutants for methods of a frozen
dataclass; an ungraded module must never be reported as a clean one). The canonical run
also exposed 16 real survivors in guardrails/report/roles/loop introduced by Plan-3a-era
churn (salvage paths, billing, import_hint) that postdated the last documented pass —
the gate was re-run, not assumed.

| Run | Mutants | Killed | Survived | No-cov | Overall | Covered |
|-----|---------|--------|----------|--------|---------|---------|
| Canonical (7 modules) | 913 | 906 | 7 | 0 | 99.2% | 99.2% |
| + post-run killing test (targeted-verified) | 913 | 907 | 6 | 0 | **99.3%** | **99.3%** |

Both denominators coincide this pass (zero no-coverage mutants). 34 new killing tests
were added across test_scope/test_guardrails/test_loop/test_roles (suite 265 → 299).

**The 6 remaining survivors are all documented equivalents, each with a written
disposition (no bare exclusions):**

1. `guardrails.x_extract_test_file__mutmut_4` — pre-documented above; Jeff-approved
   exemption 2026-07-11.
2. `report.x_mcnemar_exact__mutmut_4` — pre-documented above; Jeff-approved exemption
   2026-07-11.
3. `guardrails.x__parse_failed_test_names__mutmut_3` (`(output or "")` →
   `(output or "XXXX")`) — analytically equivalent: the fallback only fires on falsy
   input, and `"XXXX"` cannot match either FAILED-line regex (both require the literal
   substring `FAILED`), so every falsy input yields `set()` on both branches.
4. `scope.x_canary_probe__mutmut_120` (drops the explicit `waived=False` kwarg) —
   analytically AND empirically equivalent: the dataclass field default is the same
   literal `False`, and no constructed assertion can observe explicit-vs-default
   (verified: it alone survived a targeted run in which all 52 sibling survivors were
   killed by the new tests).
5. `scope.x_detect__mutmut_19` (`"tests"`→`"TESTS"`) — **environment-limited equivalent**:
   macOS APFS is case-insensitive so the path still resolves; killable on case-sensitive
   filesystems. Documented, not exempted-forever.
6. `lean.x__build_argv__mutmut_3` (`+=`→`=` on first append to an empty list) —
   analytically equivalent; extend and assign coincide on `[]`.

Honest limitation, restated: mutmut 3.6 cannot mutate dataclass-method bodies; any logic
left inside one is OUTSIDE this gate. lean.py's logic was moved to module level for
exactly this reason; the pattern is now a review checklist item.
