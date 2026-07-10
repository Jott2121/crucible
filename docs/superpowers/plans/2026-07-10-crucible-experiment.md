# Crucible Experiment Implementation Plan (Plan 2 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the pre-registered experiment: H1 (adversarial loop vs one-shot, within-lineage — a replication in a new setting) and H2 (cross-lineage GPT critic vs same-lineage Claude critic — the novel claim), producing RESULTS.md with paired statistics and full cost receipts.

**Architecture:** Research-then-freeze-then-run. The related-work sweep gates the protocol; the protocol (prose + machine-readable arms config, committed before any run) gates every paid run via a new `crucible experiment` subcommand that refuses to run against a dirty or uncommitted protocol. A cheap pilot on graph-guard gates the full arms. Analysis is `crucible report` over the receipt dirs — every published number recomputable from files.

**Tech Stack:** crucible v0.1 (merged), oracle-gate providers (Anthropic + OpenAI), mutmut>=3,<4, firecrawl/web research for the sweep.

## Global Constraints

- NOTHING PAID RUNS BEFORE THE PROTOCOL IS COMMITTED. `crucible experiment` enforces this mechanically; humans obey it too.
- The related-work sweep BLOCKS protocol freeze (spec §1b). If a published measurement of cross-lineage critics under a mechanical oracle is found, STOP and present to Jeff — H2 re-scopes or the experiment stops.
- Third-party subject selection criteria are committed BEFORE looking at candidate repos (researcher-degrees-of-freedom discipline).
- gpt-5.6 rate in `crucible.meter.RATES_EXTRA` MUST be verified against the live OpenAI pricing page (and the verification date recorded in the code comment) before the first paid GPT call. H2 runs are additionally gated on Jeff loading OpenAI credits.
- Every run is metered; receipts live under `experiments/runs/` and are committed after each arm completes (receipts are the paper's data).
- Subjects are LOCAL CLONES under `~/crucible-subjects/`, pinned by SHA, never pushed. Test-stripping happens only in clones.
- Null results are published with the same prominence (blind-oracle-pilot posture).
- A red/failed run is data, never silently rerun: reruns get a new run dir and a note in the protocol deviations log (`experiments/DEVIATIONS.md`).
- Work on branch `feat/experiment` in `~/ai-agentic-code-testing`.

---

### Task 1: Related-work sweep (BLOCKING GATE)

**Files:**
- Create: `docs/RELATED-WORK.md`

**Interfaces:**
- Produces: a claim ledger that Task 4's PROTOCOL.md cites verbatim; a GO/STOP verdict on H2 novelty.

This is a research task (no code). Method:

- [ ] **Step 1: Verify the three known prior works from their FULL texts** (not abstracts): MuTAP (arXiv 2308.16557 or its journal version — locate), AdverTest (arXiv:2602.08146), Meta ACH (FSE 2025, Harman et al.). For each record: system design (who generates mutants, who generates tests, loop structure), models used AND whether builder/critic lineages ever differ, metrics reported (any cost-per-kill or $-economics?), scale, availability (open/closed).
- [ ] **Step 2: Targeted novelty searches** (multiple phrasings each, web + arXiv + Semantic Scholar): (a) cross-model / cross-lineage / heterogeneous critic or reviewer in test generation with mutation/execution-based verdicts; (b) cost-per-kill, dollar-efficiency, or token-economics of LLM test generation; (c) anti-gaming guardrails for agent-written tests (add-only, validity gates); (d) pre-registered experiments in LLM-for-SE evaluation. Record hits AND dead ends (a documented absence is the evidence).
- [ ] **Step 3: Write `docs/RELATED-WORK.md`**: one section per system (verified facts + citations), one section per claim in spec §1b with its verdict: CONFIRMED OPEN / FOUND PUBLISHED (cite). End with the claim boundary sentence the paper will use.
- [ ] **Step 4: GATE.** If any of {cross-lineage critic under mechanical oracle, cost-per-kill economics} is FOUND PUBLISHED → STOP the plan, present the finding to Jeff with the source. Otherwise commit: `docs: related-work sweep — claim ledger; H2 and cost-economics confirmed open` and proceed.

---

### Task 2: Preflight accepts test-less subjects + `crucible experiment` subcommand

**Files:**
- Modify: `src/crucible/env.py` (preflight suite check)
- Modify: `src/crucible/runner.py` (no change expected — see step 1)
- Create: `src/crucible/experiment.py`
- Modify: `src/crucible/cli.py` (new subcommand)
- Test: `tests/test_env.py` (append), `tests/test_experiment.py`

**Interfaces:**
- Consumes: `SubjectEnv.preflight(module_path)`, `run_tests` (returncode 5 = pytest "no tests collected"), `harden`/`oneshot`/`LoopConfig`, `ReceiptWriter`, `get_provider`.
- Produces: `load_protocol(path) -> dict` (validated arms config); `run_arm(protocol: dict, arm_name: str, subject_dir: Path, runs_root: Path) -> int` (exit code, receipts written); CLI `crucible experiment PROTOCOL_JSON --arm ARM --subject SUBJECT_DIR [--runs-dir DIR]`; `assert_protocol_committed(repo_root: Path, protocol_path: Path, run=subprocess.run) -> None` raising `ProtocolError` when the protocol file is untracked, modified, or the working copy differs from HEAD.

- [ ] **Step 1: Failing test — preflight tolerates a subject with zero tests** (append to `tests/test_env.py`)

```python
def test_preflight_accepts_subject_with_no_tests(tmp_path):
    # third-party subjects get their tests stripped; "no tests collected"
    # (pytest exit 5) is a valid pristine state — crucible's job is to create tests
    import shutil, subprocess
    from pathlib import Path

    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    shutil.rmtree(subject / "tests")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    env = SubjectEnv(subject_dir=subject, tester_provider=FakeProvider([]),
                     tester_model="fake-model", critic_provider=FakeProvider([]),
                     critic_model="fake-model", module_path="subject_pkg/calc.py")
    sha = env.preflight("subject_pkg/calc.py")
    assert len(sha) == 40
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_env.py::test_preflight_accepts_subject_with_no_tests -v`
Expected: FAIL — preflight raises "subject suite is red" (pytest exits 5 on no tests, `passed=False`).

- [ ] **Step 3: Fix preflight** — in `src/crucible/env.py`, in `preflight`, replace the suite-check block's failure condition so exit code 5 passes:

```python
        suite = run_tests(self.subject_dir, run=self.run)
        # pytest exit 5 = "no tests collected": a stripped subject is a valid
        # pristine state (crucible's job is to create the tests). Anything else
        # non-zero is a red suite: hard stop before any model is called.
        if not suite.passed and suite.returncode != 5:
            raise RuntimeError(
                "subject suite is red on pristine code; hard stop before any "
                f"model is called\n{suite.output[-2000:]}"
            )
```

- [ ] **Step 4: Run to verify it passes** (and the red-suite test still fails properly)

Run: `.venv/bin/python -m pytest tests/test_env.py -q`
Expected: all pass.

- [ ] **Step 5: Failing tests — protocol loading and the committed-protocol gate** (`tests/test_experiment.py`)

```python
import json
import subprocess
from pathlib import Path

import pytest

from crucible.experiment import ProtocolError, assert_protocol_committed, load_protocol

PROTOCOL = {
    "protocol_version": 1,
    "tester": {"provider": "anthropic", "model": "claude-sonnet-5"},
    "rounds": {"max_rounds": 4, "dry_rounds": 2},
    "arms": {
        "oneshot": {"mode": "oneshot"},
        "loop-same": {"mode": "harden", "critic": {"provider": "anthropic", "model": "claude-sonnet-5"}},
        "loop-cross": {"mode": "harden", "critic": {"provider": "openai", "model": "gpt-5.6"}},
    },
}


def test_load_protocol_roundtrip(tmp_path):
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(PROTOCOL))
    loaded = load_protocol(p)
    assert loaded["arms"]["loop-cross"]["critic"]["model"] == "gpt-5.6"


def test_load_protocol_rejects_unknown_arm_mode(tmp_path):
    bad = dict(PROTOCOL, arms={"x": {"mode": "yolo"}})
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ProtocolError, match="mode"):
        load_protocol(p)


def _git_repo_with(tmp_path, name, content, committed=True):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    f = repo / name
    f.write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    if committed:
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "seed"], cwd=repo, check=True)
    return repo, f


def test_committed_protocol_passes(tmp_path):
    repo, f = _git_repo_with(tmp_path, "protocol.json", json.dumps(PROTOCOL))
    assert_protocol_committed(repo, f)  # no raise


def test_uncommitted_protocol_refused(tmp_path):
    repo, f = _git_repo_with(tmp_path, "protocol.json", json.dumps(PROTOCOL), committed=False)
    with pytest.raises(ProtocolError, match="committed"):
        assert_protocol_committed(repo, f)


def test_modified_protocol_refused(tmp_path):
    repo, f = _git_repo_with(tmp_path, "protocol.json", json.dumps(PROTOCOL))
    f.write_text(json.dumps(dict(PROTOCOL, protocol_version=2)))
    with pytest.raises(ProtocolError, match="differs from HEAD"):
        assert_protocol_committed(repo, f)
```

- [ ] **Step 6: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_experiment.py -v`
Expected: FAIL — `ModuleNotFoundError: crucible.experiment`.

- [ ] **Step 7: Implement** — `src/crucible/experiment.py`

```python
"""Pre-registration enforcement + arm runner.

`crucible experiment` runs one (arm, subject) cell of the pre-registered design. It
refuses to run unless the protocol file is committed and byte-identical to HEAD —
the mechanical form of "the protocol was frozen before the data existed."
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

VALID_MODES = ("oneshot", "harden")


class ProtocolError(RuntimeError):
    """The protocol file is invalid, uncommitted, or modified."""


def load_protocol(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("protocol_version", "tester", "rounds", "arms"):
        if key not in data:
            raise ProtocolError(f"protocol missing required key {key!r}")
    for name, arm in data["arms"].items():
        if arm.get("mode") not in VALID_MODES:
            raise ProtocolError(f"arm {name!r} has invalid mode {arm.get('mode')!r}")
        if arm["mode"] == "harden" and "critic" not in arm:
            raise ProtocolError(f"harden arm {name!r} needs a critic")
    return data


def _git(repo_root, *args, run=subprocess.run) -> str:
    proc = run(["git", *args], cwd=str(repo_root), capture_output=True, text=True)
    if proc.returncode != 0:
        raise ProtocolError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def assert_protocol_committed(repo_root, protocol_path, run=subprocess.run) -> None:
    repo_root = Path(repo_root)
    rel = str(Path(protocol_path).resolve().relative_to(repo_root.resolve()))
    tracked = _git(repo_root, "ls-files", "--", rel, run=run).strip()
    if not tracked:
        raise ProtocolError(f"{rel} is not committed; pre-registration requires a committed protocol")
    head = _git(repo_root, "show", f"HEAD:{rel}", run=run)
    if head != Path(protocol_path).read_text(encoding="utf-8"):
        raise ProtocolError(f"{rel} differs from HEAD; commit the protocol before running")


def run_arm(protocol: dict, arm_name: str, subject_dir, runs_root, module_path: str) -> int:
    """Run one cell. Imports stay local so unit tests of the gate need no providers."""
    from datetime import datetime, timezone

    from crucible.env import SubjectEnv
    from crucible.loop import LoopConfig, harden, oneshot
    from crucible.providers_ext import get_provider
    from crucible.receipts import ReceiptWriter

    arm = protocol["arms"][arm_name]
    tester = get_provider(protocol["tester"]["provider"])
    critic_cfg = arm.get("critic", protocol["tester"])
    critic = tester if critic_cfg == protocol["tester"] else get_provider(critic_cfg["provider"])

    env = SubjectEnv(
        subject_dir=Path(subject_dir),
        tester_provider=tester, tester_model=protocol["tester"]["model"],
        critic_provider=critic, critic_model=critic_cfg["model"],
        module_path=module_path,
    )
    head_sha = env.preflight(module_path)

    cfg = LoopConfig(max_rounds=protocol["rounds"]["max_rounds"],
                     dry_rounds=protocol["rounds"]["dry_rounds"], arm=arm_name)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(runs_root) / Path(subject_dir).name / f"{arm_name}-{stamp}"
    writer = ReceiptWriter(run_dir, {
        "subject": str(subject_dir), "module": module_path, "head_sha": head_sha,
        "arm": arm_name, "protocol_version": protocol["protocol_version"],
        "tester_provider": protocol["tester"]["provider"],
        "tester_model": protocol["tester"]["model"],
        "critic_provider": critic_cfg["provider"], "critic_model": critic_cfg["model"],
        "max_rounds": cfg.max_rounds, "dry_rounds": cfg.dry_rounds, "started_at": stamp,
    })
    fn = oneshot if arm["mode"] == "oneshot" else harden
    result = fn(env, cfg, on_round=writer.append)
    writer.finish(result.verdict, result.total_cost_usd, extra={
        "baseline_survivors": result.baseline_survivors,
        "baseline_all_mutants": result.baseline_all_mutants,
        "baseline_counts": result.baseline_counts,
    })
    print(f"{arm_name} on {Path(subject_dir).name}: verdict={result.verdict} "
          f"cost=${result.total_cost_usd:.4f} receipt={run_dir}")
    return 3 if result.verdict in ("aborted", "rejected") else 0
```

NOTE: check `SubjectEnv`'s actual constructor and `ReceiptWriter.finish` signature against the merged code before wiring — the shapes above match v0.1 as merged; if drift is found, match the code, not this plan.

- [ ] **Step 8: Wire the CLI** — in `src/crucible/cli.py` `main()`, add:

```python
    ep = sub.add_parser("experiment")
    ep.add_argument("protocol")
    ep.add_argument("--arm", required=True)
    ep.add_argument("--subject", required=True)
    ep.add_argument("--module", required=True)
    ep.add_argument("--runs-dir", default="experiments/runs")
```
and in the dispatch, before `_cmd_run`:
```python
    if args.cmd == "experiment":
        from pathlib import Path as _P

        from crucible.experiment import assert_protocol_committed, load_protocol, run_arm
        repo_root = _P(__file__).resolve()
        # repo root = cwd; the protocol must live in the crucible repo checkout
        assert_protocol_committed(_P.cwd(), _P(args.protocol))
        protocol = load_protocol(args.protocol)
        return run_arm(protocol, args.arm, args.subject, args.runs_dir, args.module)
```

- [ ] **Step 9: Run the suites**

Run: `.venv/bin/python -m pytest -q -m "not slow"` then `.venv/bin/python -m pytest tests/test_cli_e2e.py -q -m slow`
Expected: all green, 0 warnings.

- [ ] **Step 10: Commit**

```bash
git add src/crucible tests
git commit -m "feat: experiment runner — committed-protocol gate, arm cells, stripped-subject preflight"
```

---

### Task 3: Selection criteria (committed first), subject manifest, prep script

**Files:**
- Create: `experiments/SELECTION.md` (commit BEFORE selecting)
- Create: `experiments/subjects.json`
- Create: `experiments/prep.py`

- [ ] **Step 1: Write and COMMIT `experiments/SELECTION.md` before looking at any candidate repo:**

```markdown
# Third-party subject selection criteria (committed before selection)

Candidates come from the top of the PyPI most-downloaded list (hugovk top-pypi-packages
snapshot current at selection date), scanned IN RANK ORDER. First 2 packages meeting ALL
criteria are selected — no discretion:

1. Pure Python (no C extensions), installable editable from a git clone.
2. Permissive license (MIT/BSD/Apache).
3. Has an existing pytest test suite (which we will strip in the clone).
4. Has at least one module of 100-800 source lines of plain logic (no network/IO-heavy
   modules) — the first qualifying module in alphabetical order becomes the target.
5. mutmut 3 generates >= 40 mutants for that module in a smoke run.
6. Not authored by, contributed to, or previously analyzed by Jeff (no familiarity edge).

Exclusions and the walk order are recorded in subjects.json as selection_log.
```

```bash
git add experiments/SELECTION.md && git commit -m "experiment: freeze third-party selection criteria before selection"
```

- [ ] **Step 2: Execute the selection** (walk the ranked list, apply criteria, record every skip + reason in `selection_log`).

- [ ] **Step 3: Write `experiments/subjects.json`** — for the 3 local subjects use the CURRENT main SHA of each (`git -C ~/attrition-risk-ml rev-parse HEAD` etc.); modules chosen for headroom (NOT previously mutation-hardened):

```json
{
  "subjects": [
    {"name": "attrition-risk-ml", "source": "local:~/attrition-risk-ml", "pinned_sha": "<FILL: rev-parse>", "module": "<FILL: pick the core scoring/train module>", "strip_tests": false},
    {"name": "graph-guard", "source": "local:~/graph-guard", "pinned_sha": "<FILL>", "module": "<FILL: ppr.py or guards.py — NOT eval_metrics (already hardened; ceiling effect)>", "strip_tests": false},
    {"name": "rag-guard", "source": "local:~/rag-guard", "pinned_sha": "<FILL>", "module": "<FILL: core guard/redaction module>", "strip_tests": false},
    {"name": "<third-party-1>", "source": "pypi-git", "pinned_sha": "<FILL>", "module": "<FILL>", "strip_tests": true},
    {"name": "<third-party-2>", "source": "pypi-git", "pinned_sha": "<FILL>", "module": "<FILL>", "strip_tests": true}
  ],
  "selection_log": ["<package>: skipped — <criterion #> ..."]
}
```
(The `<FILL>` markers are selection-time values the implementer resolves and commits — they are the task's deliverable, not plan placeholders.)

- [ ] **Step 4: Write `experiments/prep.py`** (stdlib): for each subject — clone to `~/crucible-subjects/<name>` at `pinned_sha` (local clones use `git clone <path>`), `git checkout <sha>`, if `strip_tests`: `git rm -rq tests/` (or the suite dir found) + commit in clone; `pip install -e <clone>` into crucible's venv; run `crucible`'s preflight-equivalent smoke: `python -m pytest -q` accepting exit 0 or 5; `python -m mutmut --version` sanity. Print a per-subject PREPARED/FAILED table. (Implementer writes this file; ~80 lines, argparse with `--only NAME`.)

- [ ] **Step 5: Run prep for the 3 local subjects; fix environment issues; commit manifest + script + log.**

```bash
git add experiments/ && git commit -m "experiment: subjects pinned + prepared (3 local + 2 selected third-party)"
```

---

### Task 4: PROTOCOL.md + protocol.json — author, Jeff approves, freeze

**Files:**
- Create: `experiments/PROTOCOL.md`, `experiments/protocol.json`, `experiments/DEVIATIONS.md` (empty header)

- [ ] **Step 1: Author `experiments/PROTOCOL.md`** — sections, all pre-registered: claim under test (H1 replication framing + H2 novel, citing docs/RELATED-WORK.md verbatim boundaries); design (paired per subject-module; arms oneshot / loop-same / loop-cross; tester constant = claude-sonnet-5; rounds max 4, dry 2); metrics (per-mutant paired kill outcomes → McNemar exact; survivors killed; cost-per-kill from receipts; full-denominator scores both ways); exclusions (invalid/flaky generated tests are logged, not kills; aborted runs = missing cell, documented in DEVIATIONS.md); stopping rules (each arm runs once per subject; no reruns without a DEVIATIONS entry); success criteria + null interpretation for both H1 and H2 (written BEFORE data); limitations (training-data contamination of subjects; mutant-environment detection by hostile tests not closable without sandboxing; 2-run flake check; single tester model); budget posture (metered, receipts committed; gpt-5.6 rate verification required pre-H2).
- [ ] **Step 2: Author `experiments/protocol.json`** — exactly the shape Task 2's `load_protocol` validates (tester sonnet-5; the three arms; rounds 4/2).
- [ ] **Step 3: JEFF GATE.** Present both files to Jeff for approval (his name goes in PROTOCOL.md as approver). Do not commit until he approves; his approval message is quoted in the commit body.
- [ ] **Step 4: Freeze.**

```bash
git add experiments/PROTOCOL.md experiments/protocol.json experiments/DEVIATIONS.md
git commit -m "experiment: PROTOCOL frozen pre-data (approved by Jeff Otterson)"
git push -u origin feat/experiment
```

---

### Task 5: Pilot on graph-guard (GO/NO-GO GATE — first paid runs)

- [ ] **Step 1: Key check.** `python -c "import os; print(bool(os.environ.get('ANTHROPIC_API_KEY')))"` and/or `ls ~/.config/oracle-gate/anthropic.key`. Tiny ping via oracle-gate provider (one 10-token completion). If no working key/credits → STOP, ask Jeff (irreducible).
- [ ] **Step 2: Run the pilot cell pair** on the prepared graph-guard clone, module per subjects.json:

```bash
cd ~/ai-agentic-code-testing
.venv/bin/crucible experiment experiments/protocol.json --arm oneshot --subject ~/crucible-subjects/graph-guard --module <module>
.venv/bin/crucible experiment experiments/protocol.json --arm loop-same --subject ~/crucible-subjects/graph-guard --module <module>
```
- [ ] **Step 3: Inspect receipts end-to-end**: baseline measured, rounds streamed, kills named, costs per round populated (nonzero usage), verdicts sane. Run `crucible report` on the pair — paired 2x2 + McNemar print.
- [ ] **Step 4: Cost projection.** From the pilot's measured cost, project the full H1 grid (5 subjects x 2 arms) and H2 (5 x 1). Record in the report.
- [ ] **Step 5: GO/NO-GO to Jeff** with the receipts and projection. GO ⇒ Task 6. Wall-clock note: mutation runs dominate; if a subject's module makes rounds >20 min, flag before the full grid. Commit receipts: `git add experiments/runs && git commit -m "experiment: graph-guard pilot receipts (go/no-go evidence)"`.

---

### Task 6: H1 grid — 5 subjects x (oneshot, loop-same)

- [ ] **Step 1: Run the 10 cells sequentially** (same commands as pilot per subject; graph-guard's pilot cells COUNT as its cells unless DEVIATIONS says otherwise — decide in PROTOCOL.md Step 1 of Task 4, default: pilot cells count).
- [ ] **Step 2: Commit receipts after each subject completes** (crash-safe evidence): `git add experiments/runs && git commit -m "experiment: H1 receipts — <subject>"`.
- [ ] **Step 3: Interim readout** (no p-hacking — the readout is descriptive only until all cells land): `crucible report` per subject pair.

---

### Task 7: H2 arm — 5 x loop-cross (GATED on Jeff)

- [ ] **Step 1: JEFF GATE.** OpenAI credits loaded + gpt-5.6 rate verified on the live pricing page → update `RATES_EXTRA` comment with verification date, commit: `chore: gpt-5.6 rate verified <date>`.
- [ ] **Step 2: Run 5 loop-cross cells**, committing receipts per subject as in Task 6.

---

### Task 8: Analysis + RESULTS.md + wrap

- [ ] **Step 1: Compute the pre-registered readouts** exactly as PROTOCOL.md §metrics defines: per-subject paired 2x2s, pooled McNemar for H1 (loop-same vs oneshot) and H2 (loop-cross vs loop-same), cost-per-kill per arm, full-denominator mutation-score deltas. All via `crucible report` + a small `experiments/analyze.py` (stdlib, reads receipts, prints the RESULTS tables — implementer writes it, ~120 lines, with unit tests against crafted receipt dirs in `tests/test_analyze.py`).
- [ ] **Step 2: Write `experiments/RESULTS.md`**: verdicts on H1 and H2 (supported / not supported / mixed, per the protocol's pre-written interpretation rules), every table, total spend, deviations summary, limitations restated. A null is written up with the same prominence.
- [ ] **Step 3: Update README** (results summary + link), update `docs/RELATED-WORK.md` if the writing surfaced anything new, commit, push, PR `feat/experiment` → main, CI green, squash-merge.
- [ ] **Step 4: Memory sync + report to Jeff** with the RESULTS and the Plan 3 decision (skill wrapper + public flip).

---

## Self-review notes

- Spec coverage: §8 experiment (H1/H2, arms, metrics, stats, subjects, null-posture) → Tasks 1, 3, 4, 6, 7, 8. §1b related-work blocking → Task 1. Budget/meter rows → Tasks 5-7 receipts + gpt rate gate. §6 `crucible experiment` refuses dirty/uncommitted protocol → Task 2. Pilot go/no-go (§8 sequencing) → Task 5.
- Placeholder scan: `<FILL>` markers in subjects.json are selection-time deliverables resolved by Task 3's implementer, explicitly so. No TBDs elsewhere.
- Type consistency: `run_arm(protocol, arm_name, subject_dir, runs_root, module_path)` matches the CLI wiring; `assert_protocol_committed(repo_root, protocol_path)` matches tests; `LoopConfig/harden/oneshot/ReceiptWriter.finish(extra=...)` match crucible v0.1 as merged.
- Honesty checks built in: criteria-before-selection, protocol-before-data (mechanical), receipts-committed-per-subject, DEVIATIONS.md for anything off-script, pilot cells counted per a pre-declared rule.
