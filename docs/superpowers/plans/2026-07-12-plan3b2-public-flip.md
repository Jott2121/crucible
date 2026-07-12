# Plan 3b.2+3: Public Flip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the repo public as github.com/Jott2121/crucible — tool-first, every claim traceable, zero falsified statements — with the item-3 residual cleanups landed on the same branch.

**Architecture:** Truth pass first (surgical README results fix + mechanical stale-token sweep), then three small TDD code cleanups (tox.ini scan, pyproject pin + dogfood scope, import_hint threading), then the full outsider README, an adversarial claims review, a repo-sentinel audit, Jeff-gated positioning copy, and a staged flip that only Jeff triggers.

**Tech Stack:** Python 3.11+ stdlib; pytest; mutmut 3.6.0; gh CLI for the flip.

**Spec:** `docs/superpowers/specs/2026-07-12-plan3b2-public-flip-design.md`

## Global Constraints

- Branch `feat/public-flip` off `34aea91` (post-3b.1 main). Repo stays PRIVATE until Task 9, which runs only on Jeff's explicit go.
- `experiments/` is FROZEN — verified, never edited. `.superpowers/` is git-ignored and stays that way.
- Suite green under `.venv/bin/python -m pytest -q -W error` at every commit (currently 260 tests; no `timeout` wrapper — unavailable on this shell).
- No paid or Max-billed model call in any test.
- Truth sources (verbatim, from frozen `experiments/RESULTS.md` + receipts): H1 SUPPORTED, pooled exact McNemar p = 4.9×10⁻³², b = 105, c = 0, framed as a REPLICATION (MuTAP / AdverTest / Meta ACH — `docs/RELATED-WORK.md`); H2 NOT SUPPORTED, p = 0.0625, the prior 9.5×10⁻⁶⁶ was a truncation artifact (the autopsy is the finding). Lean receipts: 439,230 → 3,641 input tokens (120.6×), 25/25 survivors killed both runs, receipts `20260712T050833Z` (ambient) and `20260712T171312Z` (lean) under `~/.crucible-runs/rag-guard/`. Never state the 120.6× as a constant — always "measured on the reference run."
- Stale tokens that must appear NOWHERE outside `experiments/` and `docs/RELATED-WORK.md`: `9.5×10⁻⁶⁶`, `3.4×10⁻¹⁸`, "supported with a load-bearing caveat".
- Commit messages conventional; one task's files per commit; `git add` specific paths only.

---

### Task 1: Truth pass — surgical README results fix + sweep test

**Files:**
- Modify: `README.md` (lines 3, 15–33: the Status line and `## Results` section)
- Test: `tests/test_no_stale_claims.py` (new)

**Interfaces:**
- Produces: a repo-level invariant test later tasks must keep green: no stale token in any tracked file outside the two exempt paths.

- [ ] **Step 1: Write the failing sweep test** (`tests/test_no_stale_claims.py`, new):

```python
"""Publication invariant: retracted numbers must not appear in any tracked,
outsider-facing file. The frozen experiment report and the related-work doc
may discuss them (that IS the autopsy); everywhere else a hit is a published
falsehood. Guards the truth pass of spec 2026-07-12-plan3b2 §3."""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Exempt = files whose CONTENT is the retraction/definition itself (amended
# 2026-07-12: the original two-path tuple was underinclusive -- this test
# flagged the plan/spec docs that define it, and would flag its own STALE
# list once tracked):
#   experiments/            -- the frozen autopsy discusses the retracted number
#   docs/RELATED-WORK.md    -- prior-art discussion references it
#   docs/superpowers/       -- process specs/plans defining this sweep quote its targets
#   this test file          -- the STALE list IS the tokens
EXEMPT = ("experiments/", "docs/RELATED-WORK.md", "docs/superpowers/",
          "tests/test_no_stale_claims.py")
STALE = ["9.5×10⁻⁶⁶", "3.4×10⁻¹⁸",
         "supported with a load-bearing caveat"]


def _tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, check=True).stdout
    return [f for f in out.splitlines()
            if not any(f == e or f.startswith(e) for e in EXEMPT)]


def test_no_retracted_numbers_outside_exempt_paths():
    hits = []
    for rel in _tracked_files():
        p = REPO / rel
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for tok in STALE:
            if tok in text:
                hits.append(f"{rel}: {tok!r}")
    assert not hits, f"retracted claims still published: {hits}"
```

- [ ] **Step 2: Run to verify it fails** — `.venv/bin/python -m pytest -q tests/test_no_stale_claims.py -v`. Expected: FAIL listing `README.md` (it currently contains `9.5×10⁻⁶⁶` and the caveat phrase).

- [ ] **Step 3: Fix README surgically.** Replace line 3 (`**Status: private — pre-registered results are in.**`) with:

```markdown
**Pre-registered results are in — including a published null.**
```

Replace the entire `## Results` paragraph (current lines ~15–33) with:

```markdown
## Results

The pre-registered experiment (`experiments/PROTOCOL.md`) ran five subjects across three arms
(one-shot, same-lineage adversarial loop, cross-lineage adversarial loop). **H1** — the
adversarial loop kills more mutants than one-shot generation — is **supported**: pooled exact
McNemar p = 4.9×10⁻³², b = 105, c = 0. This **replicates** the direction established by MuTAP,
AdverTest, and Meta's ACH (see `docs/RELATED-WORK.md`) in a new agentic, repo-level, Python
setting — we claim the replication, not the idea. **H2** — a cross-lineage critic beats a
same-lineage critic on missed survivors — is **not supported** (p = 0.0625). An earlier run
showed an enormous H2 effect; the autopsy traced it to silent output truncation rejecting one
arm's rounds — an instrument artifact, not a model difference. That autopsy, and the fail-closed
instrumentation built from it, is the finding. Full tables, all three pre-declared views,
cost-per-kill, and the instrument-repair narrative: [`experiments/RESULTS.md`](experiments/RESULTS.md).
```

- [ ] **Step 4: Run the sweep test to verify it passes**, then the full suite — `.venv/bin/python -m pytest -q -W error`. Expected: 261 passed.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_no_stale_claims.py
git commit -m "fix: truth pass — README results rewritten from frozen RESULTS.md + stale-claim invariant test"
```

---

### Task 2: tox.ini [pytest] in the discovery-config scan

**Files:**
- Modify: `src/crucible/scope.py:215` (the configparser loop in `_pytest_config_sections`)
- Test: `tests/test_scope.py` (append)

**Interfaces:**
- Consumes: `_pytest_config_sections` / `_assert_fresh_file_collectable` (existing, scope.py:199/247).
- Produces: identical fail-closed behavior for `tox.ini [pytest]` sections.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_scope.py`; reuse the file's existing `_mk` helper):

```python
def test_discovery_scan_refuses_tox_ini_python_files_mismatch(tmp_path):
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "tox.ini": "[pytest]\npython_files = check_*.py\n",
    })
    with pytest.raises(RuntimeError, match="tox.ini"):
        scope_mod._assert_fresh_file_collectable(repo)


def test_discovery_scan_ignores_tox_ini_without_pytest_section(tmp_path):
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "tox.ini": "[tox]\nenvlist = py311\n",
    })
    scope_mod._assert_fresh_file_collectable(repo)  # must not raise
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest -q tests/test_scope.py -k tox -v`. Expected: the first test FAILS (no refusal raised — tox.ini is not scanned today).

- [ ] **Step 3: Implement.** In `scope.py:215`, extend the tuple:

```python
    for fname, sect in (("pytest.ini", "pytest"), ("setup.cfg", "tool:pytest"),
                        ("tox.ini", "pytest")):
```

Also update the `_pytest_config_sections` docstring's file list to include `tox.ini [pytest]`, and delete the corresponding line from the accepted-residuals note in `_assert_fresh_file_collectable`'s docstring if present (grep `tox` in the file; the residual is now closed).

- [ ] **Step 4: Run** `tests/test_scope.py` then the full suite. Expected: all pass (263).

- [ ] **Step 5: Commit**

```bash
git add src/crucible/scope.py tests/test_scope.py
git commit -m "feat: scan tox.ini [pytest] in the discovery-config refusal (residual closed)"
```

---

### Task 3: pyproject — exact mutmut pin + scope.py/lean.py into the dogfood scope

**Files:**
- Modify: `pyproject.toml` (dependencies line `"mutmut>=3,<4"`; `[tool.mutmut] source_paths`)
- Modify: `docs/MUTATION.md` (append the new dogfood pass table)

**Interfaces:**
- Consumes: the dogfood discipline in `docs/MUTATION.md` (report BOTH denominators; survivors need a documented explanation or a killing test).
- Produces: `mutmut==3.6.0` pinned; `src/crucible/scope.py` and `src/crucible/lean.py` under dogfood mutation.

- [ ] **Step 1: Pin mutmut.** In `[project] dependencies`, replace `"mutmut>=3,<4",` with:

```toml
    # Exact pin: scope.py's SRC_SHIM reads MUTANT_UNDER_TEST at call time -- a
    # mutmut 3.6.0 internal contract, not a public API (accepted residual, now pinned).
    "mutmut==3.6.0",
```

Run `.venv/bin/pip install -e ".[dev]" -q` and confirm `pip show mutmut` still reports 3.6.0.

- [ ] **Step 2: Extend the dogfood scope.** In `[tool.mutmut] source_paths`, append after `"src/crucible/roles.py",`:

```toml
    "src/crucible/scope.py",
    "src/crucible/lean.py",
]
```

- [ ] **Step 3: Run the dogfood pass** — `rm -rf mutants && .venv/bin/mutmut run` (minutes), then `.venv/bin/mutmut results`. Record: total mutants, killed, survived, no-coverage.

- [ ] **Step 4: Triage every new survivor** per MUTATION.md discipline: write a killing test in the module's test file where feasible; a genuine equivalent gets a documented entry (what the mutant is, why no test can catch it) — never a bare exclusion. Re-run until survivors are 0 or all documented.

- [ ] **Step 5: Append the pass to `docs/MUTATION.md`** as a new dated section with the same table shape as the existing ones — both denominators (overall score AND covered-code score), survivor list with dispositions.

- [ ] **Step 6: Full suite** — `.venv/bin/python -m pytest -q -W error`. Expected: all pass (count may have grown with killing tests).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml docs/MUTATION.md tests/
git commit -m "chore: pin mutmut==3.6.0 (MUTANT_UNDER_TEST coupling) + scope.py/lean.py into dogfood mutation scope"
```

---

### Task 4: import_hint threading on the tool path

**Files:**
- Modify: `src/crucible/cli.py` (extract `_derive_run_scope`; use it in `_cmd_run`, currently lines ~54–66)
- Test: `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `scope_mod.detect` → `ScopePlan(needs_src_shim, also_copy, pytest_args)`; `SubjectEnv(scope=...)` already reads `scope["import_hint"]` (env.py:190–197).
- Produces: `_derive_run_scope(subject: Path, module: str) -> dict` — module-level, pure; on src-layouts the dict gains `"import_hint"`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_cli.py`):

```python
def test_derive_run_scope_threads_import_hint_on_src_layout(tmp_path):
    from crucible.cli import _derive_run_scope
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text("X = 1\n")
    scope = _derive_run_scope(tmp_path, "src/mod.py")
    assert scope["import_hint"] == (
        "Import the module under test as `mod` -- the src/ prefix is not "
        "importable in the test environment.")
    assert "conftest.py" in scope["extra_files"]


def test_derive_run_scope_no_hint_on_package_dir(tmp_path):
    from crucible.cli import _derive_run_scope
    (tmp_path / "mypkg").mkdir()
    (tmp_path / "mypkg" / "mod.py").write_text("X = 1\n")
    scope = _derive_run_scope(tmp_path, "mypkg/mod.py")
    assert "import_hint" not in scope
    assert scope["also_copy"] == ["mypkg"]
```

- [ ] **Step 2: Run to verify failure** — `ImportError: cannot import name '_derive_run_scope'`.

- [ ] **Step 3: Implement.** In `cli.py`, extract the existing inline block (lines ~54–66) into a module-level function and extend it; `_cmd_run` calls it:

```python
def _derive_run_scope(subject: Path, module: str) -> dict:
    """Derive the run scope the SAME way `crucible scope` does, so harden's
    preflight writes the byte-identical [tool.mutmut] (+ conftest shim) that
    scope's canary proved. On src-layouts, also thread the bare-module
    import_hint into the tester/critic prompts (env.py reads
    scope["import_hint"]) -- generated tests import `mod`, never `src.mod`
    (the sandbox path the shim creates; closes the ledger's src-layout
    inefficiency residual)."""
    plan = scope_mod.detect(subject, module)
    run_scope: dict = {"also_copy": plan.also_copy,
                       "pytest_args": plan.pytest_args or None}
    if plan.needs_src_shim:
        run_scope["extra_files"] = {"conftest.py": scope_mod.SRC_SHIM}
        modname = module[:-3].replace("/", ".")
        if modname.startswith("src."):
            modname = modname[len("src."):]
        run_scope["import_hint"] = (
            f"Import the module under test as `{modname}` -- the src/ prefix "
            "is not importable in the test environment.")
    return run_scope
```

In `_cmd_run`, replace the inline derivation with `run_scope = _derive_run_scope(subject, args.module)` (keep the `SubjectEnv(..., scope=run_scope)` call unchanged). Preserve any surrounding comments that still apply; delete the ones the docstring now carries.

- [ ] **Step 4: Run** `tests/test_cli.py` then the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/cli.py tests/test_cli.py
git commit -m "feat: thread src-layout import_hint through the harden/oneshot path (residual closed)"
```

---

### Task 5: The outsider README

**Files:**
- Modify: `README.md` (full rewrite; the Task-1 Results block is carried over verbatim)

**Interfaces:**
- Consumes: Task 1's Results block (verbatim), Global Constraints truth sources, actual CLI flags (`crucible scope <subject> --module M`; `crucible harden <subject> --module M --tester claude-cli --critic claude-cli --runs-dir <dir>`; `--runs-dir` defaults to `./runs` and refuses a dir inside the subject).
- Produces: the outsider-facing README Task 6 audits and Task 8's copy echoes.

- [ ] **Step 1: Replace `README.md` with** (Results section = Task 1's text, inserted where marked):

````markdown
# crucible

[![ci](https://github.com/Jott2121/crucible/actions/workflows/ci.yml/badge.svg)](https://github.com/Jott2121/crucible/actions/workflows/ci.yml)

**Your AI wrote the tests. Who tested the tests?**

Coverage measures what ran, not what would be caught. Mutation testing injects real defects
and counts how many your suite kills — and AI-written suites routinely leave survivors.
crucible closes the loop: a **Tester** agent writes tests, **mutmut** finds the survivors —
injected defects no test caught — and a **Critic** agent is handed the named survivors and
writes tests to kill exactly those. Every verdict is mechanical: pytest kills the mutant or
it survives. **No model ever grades model output.**

## First win — free, no model, no keys (~10 minutes)

Find out what your existing tests miss, on your own repo:

    git clone https://github.com/Jott2121/crucible && pip install -e "./crucible[dev]"
    cd /path/to/your-repo-clone       # work in a clone: crucible writes scope config
    crucible scope . --module yourpkg/yourmodule.py
    mutmut run && mutmut results      # survivors = injected bugs your tests never caught

`crucible scope` detects your layout, writes the mutation scope, and **proves** a fresh test
file is collectable before anything else runs (a canary probe; it refuses — exit 4 — rather
than guess). No AI is involved yet: the survivor count is plain mutation testing on your suite.

## Then harden — the adversarial loop

    crucible harden . --module yourpkg/yourmodule.py \
        --tester claude-cli --critic claude-cli --runs-dir ~/.crucible-runs/yourrepo

With `claude-cli`, model calls run through Claude Code headless on your Claude subscription —
**$0 metered spend**, and every receipt carries `billing: max-plan` so plan-covered shadow
dollars are never mistaken for an invoice. No subscription? `--tester anthropic` uses the
metered API via `ANTHROPIC_API_KEY`.

Lean invocation is the default: the subprocess runs with `--tools ""`, collapsing Claude
Code's agent loop to a single completion. On the reference run (`rag_guard/guard.py`), that
took the harden from **439,230 to 3,641 input tokens (120.6×), with identical results — the
same 25/25 surviving mutants killed** (receipts `20260712T050833Z` vs `20260712T171312Z`).
Measured on that run's receipts, not a universal constant. `CRUCIBLE_LEAN=0` restores the
ambient invocation.

## Receipts are the product

Every run writes a receipt directory:

    meta.json         # models, billing (api vs max-plan), lean_isolation rung, scope commit
    receipt.jsonl     # one line per round: tokens in/out, cost, kills, survivors, prompt hash
    result.json       # verdict + totals

Generated tests land on a **local branch only** — never main, and opening a PR is strictly
opt-in. If the canary can't prove your scope, crucible refuses instead of spending tokens.

<!-- Task 1's Results section goes here, verbatim -->

## Why trust this

The claims above are checkable: the experiment was pre-registered before results existed
(`experiments/PROTOCOL.md`), the null is published at the same prominence as the positive
result, the prior art is cited rather than rediscovered (`docs/RELATED-WORK.md`), and the
tool is dogfooded — crucible's own modules run under the same mutation gate, current score
and survivor dispositions in `docs/MUTATION.md`.

## Honest limitations

- Python + pytest repos only; layout heuristics target well-formed projects — a repo the
  canary can't validate is a refusal, not a guess.
- mutmut is pinned exactly (3.6.0): the src-layout shim relies on a mutmut-internal contract.
- The `claude-cli` provider has no mechanical truncation check (the CLI exposes no output
  cap); disclosed in the provider docstring.
- The 120.6× lean result is one module, one apples-to-apples pair of runs. Your ratio will
  differ; your receipts will tell you.

## How it works

    Tester (writes tests) ──> mutmut (injects defects, counts kills)
          ^                        │ named survivors
          └──── Critic (kills exactly those) <──┘   ... until dry or round cap

Built on [oracle-gate](https://github.com/Jott2121/oracle-gate) (survivor triage, provenance,
providers). MIT license.
````

Insert Task 1's `## Results` block at the marked comment (and delete the marker). Verify every command against the actual CLI (`crucible scope --help`, `crucible harden --help`) before committing — any flag mismatch is a defect.

- [ ] **Step 2: Run the sweep + suite** — `.venv/bin/python -m pytest -q -W error`. Expected: all pass (the invariant test holds).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: outsider README — free diagnose first, harden second, receipts as the product"
```

---

### Task 6: Adversarial claims review (opus, blocking)

**Files:** none (review artifact: `.superpowers/sdd/claims-audit-3b2.md`, git-ignored)

- [ ] **Step 1:** Dispatch an opus reviewer with README.md + the §7 copy drafts + access to `experiments/RESULTS.md`, receipts dirs, and the code. Contract: walk EVERY factual sentence; map each to its source (RESULTS.md line / receipt path / code file:line); any unsourced or overstated claim is a finding. Verify the quickstart commands against the real CLI by running `--help`.
- [ ] **Step 2:** Fix wave for any findings; re-review until clean. Record the audit at `.superpowers/sdd/claims-audit-3b2.md`.

---

### Task 7: repo-sentinel audit + fix wave

**Files:** per findings (fixes to `feat/public-flip`)

- [ ] **Step 1:** Invoke the repo-sentinel skill on the repo (orchestrator-level; hiring-readiness checklist: security, correctness, README-vs-code drift, legibility). Drift is load-bearing — it mechanically backstops Task 5 vs the code.
- [ ] **Step 2:** Fix wave for findings; suite green; commit per sentinel convention.

---

### Task 8: Positioning copy (Jeff-gated)

**Files:**
- Create: `~/Desktop/crucible-launch.txt` (plain ASCII, NOT in the repo)

- [ ] **Step 1:** Write the launch file containing: (a) repo description — `Adversarial test-hardening for AI-written code: a Tester writes tests, mutation testing finds what they miss, a Critic kills the named survivors. Mechanical verdicts, mutation-kill receipts, $0 on a Claude subscription.` (b) topics — `mutation-testing, ai-generated-code, testing, llm, agents, pytest, mutmut, test-generation, claude` (c) a ~150-word launch blurb: honest headline = published null + truncation autopsy + the 120.6× receipt; explicitly a replication of the MuTAP/AdverTest/ACH direction in a new setting; no invented novelty; Jeff's plain voice, no AI tells, minimal em-dashes.
- [ ] **Step 2:** `open ~/Desktop/crucible-launch.txt`; Jeff edits/approves the copy. His approval gates Task 9.

---

### Task 9: The flip (staged; JEFF'S BUTTON)

**Files:** none (GitHub settings via gh)

- [ ] **Step 1:** Merge `feat/public-flip` to main via PR (CI green), same two-step hygiene as 3b.1.
- [ ] **Step 2:** Present Jeff the staged commands; run them ONLY on his explicit go, in order:

```bash
gh repo rename crucible --yes                                   # old URL 301-redirects
gh repo edit --description "<approved description from Task 8>"
gh repo edit --add-topic mutation-testing --add-topic ai-generated-code --add-topic testing \
  --add-topic llm --add-topic agents --add-topic pytest --add-topic mutmut \
  --add-topic test-generation --add-topic claude
gh repo edit --visibility public --accept-visibility-change-consequences
```

- [ ] **Step 3: Post-flip verification:** logged-out fetch (`curl -s https://github.com/Jott2121/crucible | grep -c "Who tested the tests"` ≥ 1); CI badge resolves (HTTP 200); old URL redirects; `gh repo view --json visibility` says PUBLIC. Record in ledger + memory + wiki build log.

---

## Self-Review Notes

**Spec coverage:** §3 truth pass → Task 1 (surgical fix + invariant test; the sweep is a permanent test, stronger than a one-off grep); §4 item-3 cleanups → Tasks 2–4 (pin folded into Task 3 with the dogfood run, same file); §5 README → Task 5 (full text embedded; Results carried from Task 1); §6 sentinel → Task 7; §7 copy → Task 8 (drafts verbatim from spec); §8 flip → Task 9 (staged, Jeff-gated, post-flip checks); §9 testing/review → TDD in Tasks 1–4 + Task 6 adversarial claims review; §10 risks → truth-first ordering + invariant test + "reference run" phrasing in Task 5; §11 YAGNI respected (no PyPI, no docs site, no art, no auto-posting).

**Placeholder scan:** none — Task 5 contains the complete README text (one deliberate insertion marker consumed within the same task); Task 8's blurb has its content requirements enumerated (it is Jeff-voice prose that he gates, with description + topics fully drafted).

**Type consistency:** `_derive_run_scope(subject, module) -> dict` consistent between Task 4's test and implementation; stale-token list identical in Task 1's test and Global Constraints; receipt IDs and numbers identical across Tasks 1/5 and Global Constraints; `("tox.ini", "pytest")` tuple form matches the existing loop's shape.

**Sequencing note:** Task 1 lands the truth surgically BEFORE the bigger rewrite so the repo never sits mid-plan with the falsehood live; Task 5 then subsumes it with the same block; the invariant test keeps both honest through every later task.
