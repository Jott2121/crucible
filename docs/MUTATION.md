# Mutation-Survivor Triage

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
