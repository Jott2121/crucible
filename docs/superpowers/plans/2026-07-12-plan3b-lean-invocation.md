# Plan 3b.1: Lean claude -p Invocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut the input tokens per hardened module by an order of magnitude via `--tools ""` (which removes the built-in tool schemas AND collapses `claude -p`'s agent loop to one turn), proven on an apples-to-apples re-harden of `rag_guard/guard.py` that still kills its baseline survivors.

**Architecture:** A new `src/crucible/lean.py` holds a `LeanProfile` (isolation intent as a simple interface) whose `build()` turns intent into `(argv, cwd)` — a deep-module seam hiding the CLI-flag mechanics. `ClaudeCLIProvider` gains an optional `lean_profile`, defaulting to the lean rung, with a `CRUCIBLE_LEAN=0` escape hatch. `meta.json` records the rung. `loop.py`, `guardrails.py`, `RoundRecord`, and `receipt.jsonl` are untouched.

**Tech Stack:** Python 3.11+ stdlib only (subprocess); pytest; Claude Code headless (`claude -p`, CLI 2.1.207).

**Spec:** `docs/superpowers/specs/2026-07-12-plan3b-lean-invocation-design.md` (read the 2026-07-12 AMENDMENT — it is the authority; sections 3-6 are superseded).

## Global Constraints

- **Base branch: `feat/lean-invocation` off `28c58fc`** (gate-7 cache-token summing). NOT `f6d058b`.
- Stdlib only; no new pip dependencies.
- TDD every code task; full suite green under `.venv/bin/python -m pytest -q -W error` at every commit (no `timeout` wrapper — absent on this shell).
- **No paid or Max-billed model call in any test (fakes only).** The only sanctioned live calls are Task 1 (done) and Task 5 (proof run).
- `loop.py`, `guardrails.py` untouched. `experiments/` frozen. `RoundRecord`/`receipt.jsonl` schema unchanged — one new `meta.json` field with a legacy-safe default (`"ambient"`).
- **The flags are probe-validated (Task 1):** `--tools ""` (disable all built-in tools) is the primary lever; `--setting-sources ""` and `--strict-mcp-config` are cheap add-ons. `CLAUDE_CONFIG_DIR` is NOT used (dropped). No retry/fallback machinery (the auth instability was a harness artifact, retracted).
- Comments state constraints, not narration. Plain-ASCII CLI output.
- Commit messages: conventional, one task's files per commit, `git add` specific paths only.

---

### Task 1: Isolation probe — DONE (2026-07-12, commits 090706d / b656065)

Recorded in `docs/superpowers/PROBE-RESULTS-3b.md`. Outcome that drives Tasks 2-5:

```
baseline (no flags):        num_turns=4   in=119,229   out=10,371   valid test
lean (--tools "" et al.):   num_turns=1   in=  1,593   out= 6,172   valid test   => ~75x
```

- **DEFAULT lean profile** = `--tools ""  --setting-sources ""  --strict-mcp-config`, no cwd override, no `CLAUDE_CONFIG_DIR`.
- `--tools ""` removes built-in tool schemas (the ~20k bulk) AND collapses the agent to 1 turn.
- No auth-class fallback needed (the "Not logged in" failures were a bash-harness artifact, not real).
- `scripts/isolation_probe.py` and `scripts/measure_tester.py` are the throwaway probes; leave them in `scripts/` as evidence, not imported by the package.

---

### Task 2: LeanProfile + build() (the deep-module seam)

**Files:**
- Create: `src/crucible/lean.py`
- Test: `tests/test_lean.py` (new)

**Interfaces:**
- Consumes: nothing (pure stdlib).
- Produces:
  - `LeanProfile` frozen dataclass: `tools: str | None = None`, `setting_sources: str | None = None`, `strict_mcp: bool = False`, `cwd: Path | None = None`, `name: str = "ambient"`.
  - `LeanProfile.build() -> tuple[list[str], str | None]` returning `(argv_extension, cwd_or_None)`.
  - Constants: `AMBIENT = LeanProfile(name="ambient")` and `DEFAULT_LEAN = LeanProfile(tools="", setting_sources="", strict_mcp=True, name="tools-off")`.

- [ ] **Step 1: Write the failing tests** (`tests/test_lean.py`, new):

```python
from pathlib import Path

from crucible.lean import AMBIENT, DEFAULT_LEAN, LeanProfile


def test_ambient_adds_nothing():
    argv, cwd = AMBIENT.build()
    assert argv == [] and cwd is None and AMBIENT.name == "ambient"


def test_default_lean_disables_tools_and_settings():
    argv, cwd = DEFAULT_LEAN.build()
    # --tools "" is the primary lever; order: tools, strict-mcp, setting-sources
    assert argv == ["--tools", "", "--strict-mcp-config", "--setting-sources", ""]
    assert cwd is None and DEFAULT_LEAN.name == "tools-off"


def test_tools_empty_string_is_emitted_not_skipped():
    # "" is a real value (disable all tools); None means "don't pass the flag"
    argv, _ = LeanProfile(tools="").build()
    assert argv == ["--tools", ""]
    argv2, _ = LeanProfile(tools=None).build()
    assert "--tools" not in argv2


def test_cwd_passthrough():
    _, cwd = LeanProfile(cwd=Path("/tmp/x")).build()
    assert cwd == "/tmp/x"
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest -q tests/test_lean.py -v`. Expected: `ModuleNotFoundError: crucible.lean`.

- [ ] **Step 3: Implement `src/crucible/lean.py`:**

```python
"""Isolation intent for a claude -p subprocess, expressed as a simple interface
over hidden CLI-flag mechanics (deep-module seam). A default claude -p call is an
AGENT: it inherits the built-in tool schemas (~20k tokens) and runs multiple
internal turns, each re-reading that cached context -- ~439k across a harden.
`--tools ""` removes the tool schemas AND collapses the loop to one turn (Task 1:
119,229 -> 1,593 on the tester call, ~75x). --setting-sources ""/--strict-mcp-config
are cheap add-ons. Tokens validated by scripts/measure_tester.py; see
docs/superpowers/PROBE-RESULTS-3b.md."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LeanProfile:
    tools: str | None = None            # "" disables ALL built-in tools (primary lever)
    setting_sources: str | None = None  # "" loads no setting sources (skills, CLAUDE.md)
    strict_mcp: bool = False
    cwd: Path | None = None
    name: str = "ambient"

    def build(self) -> tuple[list[str], str | None]:
        argv: list[str] = []
        if self.tools is not None:
            argv += ["--tools", self.tools]
        if self.strict_mcp:
            argv.append("--strict-mcp-config")
        if self.setting_sources is not None:
            argv += ["--setting-sources", self.setting_sources]
        cwd = str(self.cwd) if self.cwd is not None else None
        return argv, cwd


AMBIENT = LeanProfile(name="ambient")
DEFAULT_LEAN = LeanProfile(tools="", setting_sources="", strict_mcp=True, name="tools-off")
```

- [ ] **Step 4: Run** `tests/test_lean.py` then the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/lean.py tests/test_lean.py
git commit -m "feat: LeanProfile — --tools '' isolation intent behind a build() seam (Task 1 lever)"
```

---

### Task 3: Wire LeanProfile into ClaudeCLIProvider + escape hatch

**Files:**
- Modify: `src/crucible/providers_ext.py` (`ClaudeCLIProvider.__init__` and `complete_with_usage`)
- Test: `tests/test_providers_ext.py` (append; update existing fakes' signatures)

**Interfaces:**
- Consumes: `crucible.lean.{AMBIENT, DEFAULT_LEAN}` (Task 2).
- Produces: `ClaudeCLIProvider(run=..., lean_profile=None)`. When `lean_profile is None`: `AMBIENT` if `os.environ.get("CRUCIBLE_LEAN") == "0"`, else `DEFAULT_LEAN`. `complete_with_usage` appends `build()`'s argv to the base command and passes `cwd=`. Exposes `self.isolation_name` (the profile's `name`). Cache-token summing (gate-7) is preserved.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_providers_ext.py`; add `import os` if absent):

```python
def test_claude_cli_applies_lean_argv_and_cwd():
    from crucible.lean import LeanProfile
    from crucible.providers_ext import ClaudeCLIProvider
    calls = {}

    def fake_run(cmd, input=None, capture_output=True, text=True, timeout=None, cwd=None):
        calls["cmd"], calls["cwd"] = cmd, cwd
        return _FakeProc(stdout=_cli_envelope("hi", 10, 2))

    prof = LeanProfile(tools="", strict_mcp=True, name="tools-off")
    p = ClaudeCLIProvider(run=fake_run, lean_profile=prof)
    p.complete_with_usage("SYS", "USER", model="claude-sonnet-5")
    assert "--tools" in calls["cmd"] and "--strict-mcp-config" in calls["cmd"]
    assert calls["cmd"][calls["cmd"].index("--tools") + 1] == ""   # disable all tools
    assert calls["cwd"] is None
    assert p.isolation_name == "tools-off"


def test_claude_cli_defaults_to_lean_and_escape_hatch(monkeypatch):
    from crucible.providers_ext import ClaudeCLIProvider
    seen = {}

    def fake_run(cmd, input=None, capture_output=True, text=True, timeout=None, cwd=None):
        seen["cmd"] = cmd
        return _FakeProc(stdout=_cli_envelope("hi", 10, 2))

    # default (no profile, no env) -> lean
    monkeypatch.delenv("CRUCIBLE_LEAN", raising=False)
    p = ClaudeCLIProvider(run=fake_run)
    p.complete_with_usage("S", "U")
    assert "--tools" in seen["cmd"] and p.isolation_name == "tools-off"

    # escape hatch -> ambient
    monkeypatch.setenv("CRUCIBLE_LEAN", "0")
    p2 = ClaudeCLIProvider(run=fake_run)
    p2.complete_with_usage("S", "U")
    assert "--tools" not in seen["cmd"] and p2.isolation_name == "ambient"
```

Update the EXISTING `fake_run` in `test_claude_cli_provider_parses_text_and_usage` (and any other `ClaudeCLIProvider` fake in the file) to accept `cwd=None` in its signature, so the new `cwd=` argument at the call site does not break it.

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest -q tests/test_providers_ext.py -k "lean or escape or parses_text" -v`. Expected: FAIL (`__init__` takes no `lean_profile`; `cwd` not passed).

- [ ] **Step 3: Implement.** In `providers_ext.py` add `import os` at top; change `ClaudeCLIProvider`:

```python
    def __init__(self, run=subprocess.run, lean_profile=None):
        self._run = run
        if lean_profile is None:
            from crucible.lean import AMBIENT, DEFAULT_LEAN
            lean_profile = AMBIENT if os.environ.get("CRUCIBLE_LEAN") == "0" else DEFAULT_LEAN
        self._profile = lean_profile
        self.isolation_name = lean_profile.name

    def complete_with_usage(self, system, user, model=None):
        model = model or self.default_model
        argv, cwd = self._profile.build()
        cmd = ["claude", "-p", "--output-format", "json",
               "--model", model, "--system-prompt", system] + argv
        try:
            proc = self._run(cmd, input=user, capture_output=True, text=True,
                             timeout=self.request_timeout, cwd=cwd)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "claude CLI not found on PATH; install Claude Code or use an API provider"
            ) from exc
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p exited {proc.returncode}: {(proc.stderr or '')[-800:]}")
        data = self._extract_result(proc.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"claude -p reported an error: {data.get('result', '')[:800]}")
        u = data.get("usage") or {}
        usage_in = (int(u.get("input_tokens") or 0)
                    + int(u.get("cache_creation_input_tokens") or 0)
                    + int(u.get("cache_read_input_tokens") or 0))
        return data.get("result", ""), Usage(usage_in, int(u.get("output_tokens") or 0))
```

Update the class docstring's opening to note the lean-by-default behavior and the `CRUCIBLE_LEAN=0` escape hatch (keep the existing envelope/usage notes).

- [ ] **Step 4: Run** the provider tests then the full suite `.venv/bin/python -m pytest -q -W error`. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/providers_ext.py tests/test_providers_ext.py
git commit -m "feat: ClaudeCLIProvider lean-by-default (--tools '') + CRUCIBLE_LEAN=0 escape hatch"
```

---

### Task 4: Record the isolation rung in meta.json + report

**Files:**
- Modify: `src/crucible/cli.py` (`_cmd_run` meta dict)
- Modify: `src/crucible/report.py` (`summarize`)
- Test: `tests/test_receipts.py`, `tests/test_report.py` (append)

**Interfaces:**
- Consumes: `getattr(provider, "isolation_name", "ambient")` (Task 3).
- Produces: `meta.json` gains `"lean_isolation"` (`"ambient"` default for legacy/non-CLI providers). `summarize(run)` surfaces `"lean_isolation": meta.get("lean_isolation", "ambient")`. No served/fallback field — there is no fallback.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_report.py`:

```python
def test_summarize_surfaces_lean_isolation():
    base = {"meta": {"arm": "harden"}, "rounds": [],
            "result": {"verdict": "dry", "total_cost_usd": 0.0, "baseline_survivors": []}}
    assert summarize(base)["lean_isolation"] == "ambient"
    lean = dict(base, meta={"arm": "harden", "lean_isolation": "tools-off"})
    assert summarize(lean)["lean_isolation"] == "tools-off"
```

Append to `tests/test_receipts.py` (mirror the Plan 3a Task 2 CLI-meta test; a `fake` provider has no `isolation_name`, so it defaults to `"ambient"`):

```python
def test_cli_meta_records_lean_isolation(tmp_path, subject_clone):
    import json
    from crucible import cli
    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps(["```python\ndef test_x():\n    assert True\n```"]))
    cli.main(["oneshot", str(subject_clone), "--module", "subject_pkg/calc.py",
              "--tester", "fake", "--fake-replies", str(replies),
              "--runs-dir", str(tmp_path / "runs")])
    run_dir = next((tmp_path / "runs").iterdir())
    meta = json.loads((run_dir / "meta.json").read_text())
    assert meta["lean_isolation"] == "ambient"   # fake has no isolation_name
```

(If the `subject_clone` fixture / `oneshot` invocation differs, mirror the existing `test_cli_meta_records_billing` test added in Plan 3a Task 2 — same pattern, new key.)

- [ ] **Step 2: Run to verify failure** — `KeyError: 'lean_isolation'`.

- [ ] **Step 3: Implement.** In `cli.py`'s `_cmd_run` meta dict, after the `"tester_billing"`/`"critic_billing"` entries, add:

```python
        "lean_isolation": getattr(tester, "isolation_name", "ambient"),
```

In `report.py`'s `summarize`, add to the returned dict:

```python
        "lean_isolation": run["meta"].get("lean_isolation", "ambient"),
```

- [ ] **Step 4: Run the full suite** — `.venv/bin/python -m pytest -q -W error`. Expected: all pass (legacy fixtures default to `"ambient"`).

- [ ] **Step 5: Commit**

```bash
git add src/crucible/cli.py src/crucible/report.py tests/test_receipts.py tests/test_report.py
git commit -m "feat: record lean_isolation rung in meta and surface it in summarize"
```

---

### Task 5: Proof run — re-harden guard.py, prove tokens AND efficacy (gate, orchestrator drives)

**Files:** none in this repo (receipts land in rag-guard's `.crucible-runs/`; generated tests on its local branch — discarded after the numbers are read).

**Interfaces:** consumes the whole chain end to end; produces both the token comparison and the mutation-kill comparison that close item 1.

- [ ] **Step 1:** Confirm `feat/lean-invocation` full suite green (`.venv/bin/python -m pytest -q -W error`).
- [ ] **Step 2:** On a THROWAWAY branch of rag-guard, run the loop against `rag_guard/guard.py` (the `harden-tests` skill or `crucible harden ... --tester claude-cli --critic claude-cli`), lean default active (do NOT set `CRUCIBLE_LEAN=0`).
- [ ] **Step 3: TOKENS.** Read the new receipt's per-round `usage_in` (cache-summed) and `meta.json` `lean_isolation == "tools-off"`. Verify total input is an order of magnitude below the 439,230 baseline (`~/.crucible-runs/rag-guard/20260712T050833Z-rag-guard-harden`).
- [ ] **Step 4: EFFICACY (the real risk).** Verify the lean run still KILLS the module's baseline survivors comparably to the ambient gate-7 run (which killed 25: tester 23 + critic 2). If kills drop materially, STOP and report — the single-turn tool-less tester may need 2 turns; bring the tradeoff to Jeff rather than shipping a cheaper-but-weaker loop.
- [ ] **Step 5:** Confirm `billing: max-plan`, $0 metered. Independent reviewer (opus) verifies tokens + kills against the baseline receipt. Discard the rag-guard throwaway branch (PR is Jeff's separate call). Record before/after numbers + run dir in the memory file and wiki build log. Jeff approves the gate by name; item 1 complete.

---

## Self-Review Notes

**Spec coverage (post-amendment):** amendment lever (`--tools ""`) -> Tasks 2-3; LeanProfile seam -> Task 2; provider wiring + escape hatch -> Task 3; meta recording -> Task 4; token proof + efficacy -> Task 5; §7 testing -> per-task TDD + Task 5 live proof. Dropped by amendment (and absent here): CLAUDE_CONFIG_DIR, ephemeral config dir, bounded auth fallback, retry-with-backoff.

**Placeholder scan:** none — every code step is complete; Task 4's fixture caveat names the exact existing test to mirror.

**Type consistency:** `LeanProfile` fields and `build() -> (argv, cwd)` 2-tuple consistent across Tasks 2/3; `isolation_name` attr and `AMBIENT`/`DEFAULT_LEAN` constants consistent across Tasks 2/3/4; `lean_isolation` meta key and `"ambient"` default consistent across Task 4's cli/report/tests. `build()` returns a 2-tuple (argv, cwd) — no env — because no flag needs an env override after dropping CLAUDE_CONFIG_DIR.

**Efficacy is the one open risk (recorded):** the token win is proven (Task 1, ~75x); whether single-turn tool-less generation kills mutants as well as multi-turn is unproven and is Task 5 Step 4's job. crucible's mutation loop is the external verifier, so the model needs no self-verify tools — the hypothesis is that efficacy holds — but it is a live gate, not an assumption.
