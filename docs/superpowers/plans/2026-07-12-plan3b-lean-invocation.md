# Plan 3b.1: Lean claude -p Invocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut the ~439,230 input tokens per hardened module (inherited session preload) by an order of magnitude by isolating the `claude -p` subprocess config, proven on an apples-to-apples re-harden of `rag_guard/guard.py`.

**Architecture:** A new `src/crucible/lean.py` holds a `LeanProfile` (isolation intent as a simple interface) whose `build()` turns intent into the concrete `(argv, env, cwd)` triple — a deep-module seam that hides the CLI-flag mechanics. `ClaudeCLIProvider` gains an optional `lean_profile`, defaulting to the probe-chosen rung, with a `CRUCIBLE_LEAN=0` escape hatch and one bounded auth-class fallback. `meta.json` records the isolation rung. `loop.py`, `guardrails.py`, `RoundRecord`, and `receipt.jsonl` are untouched.

**Tech Stack:** Python 3.11+ stdlib only (subprocess); pytest; Claude Code headless (`claude -p`).

**Spec:** `docs/superpowers/specs/2026-07-12-plan3b-lean-invocation-design.md`

## Global Constraints

- **Base branch: `feat/lean-invocation` off `28c58fc`** (the gate-7-fixed state, which sums cache tokens in `providers_ext.py`). NOT `f6d058b` — that squash predates the gate-7 fixes and would reintroduce the cache-token undercount, making the whole measurement meaningless.
- Stdlib only; no new pip dependencies.
- TDD every code task; full suite green under `.venv/bin/python -m pytest -q -W error` at every commit (`timeout` is absent on this macOS shell — do not wrap pytest in it).
- **No paid or Max-billed model call in any test (fakes only).** The ONLY sanctioned live calls are Task 1's isolation probe and Task 6's proof run.
- `loop.py`, `guardrails.py` untouched. `experiments/` frozen. `RoundRecord`/`receipt.jsonl` schema unchanged — one new `meta.json` field with a legacy-safe default (`"ambient"`).
- **PROBE-VALIDATED tokens:** the exact CLI flag tokens in `LeanProfile.build()` and the chosen default/fallback rungs are pinned by Task 1's probe table — the probe is the source of truth. The code below uses candidate tokens (`--strict-mcp-config`, `--setting-sources`, `CLAUDE_CONFIG_DIR`); if Task 1 shows a token differs or a rung fails auth, adjust `build()`, the profile constants, and their tests to match, and note the change in the commit.
- Comments state constraints, not narration. Plain-ASCII CLI output.
- Commit messages: conventional, one task's files per commit, `git add` specific paths only.

---

### Task 1: Isolation probe (the spike — mechanism-check before any code)

**Files:**
- Create: `scripts/isolation_probe.py` (throwaway-grade; NOT imported by the package)
- Create: `docs/superpowers/PROBE-RESULTS-3b.md` (the recorded rung table + decision)

**Interfaces:**
- Consumes: the `claude` CLI on PATH (logged in to Max).
- Produces: a printed rung table `(rung -> auth_ok, completion_ok, input_tokens)` and a recorded DECISION: the chosen **default** rung (lowest input tokens with `auth_ok`), the **fallback** rung (safest `auth_ok` rung), and the exact argv/env each uses. These feed Tasks 2-5. No package code depends on this script.

- [ ] **Step 1: Ground the flag names (do not trust memory).** Run and read:

```bash
claude --help 2>&1 | grep -iE "mcp|setting|config|system-prompt" || claude --help 2>&1 | head -60
```

Record in `docs/superpowers/PROBE-RESULTS-3b.md` which of these actually exist in this CLI version: `--strict-mcp-config`, `--mcp-config`, `--setting-sources`, `--settings`, and whether `CLAUDE_CONFIG_DIR` is documented. If a candidate flag is absent, substitute the real one the help text shows before Step 3.

- [ ] **Step 2: Write `scripts/isolation_probe.py`:**

```python
#!/usr/bin/env python3
"""Isolation probe (Plan 3b.1 Task 1, mechanism-check). Measures input-token
cost and auth survival of `claude -p` under escalating config isolation.
Throwaway grade: run it, read the table, record the winning rung in
docs/superpowers/PROBE-RESULTS-3b.md. Not imported by the package. $0 metered
(Max plan); a handful of trivial calls."""
import json
import os
import subprocess
import tempfile

MODEL = "claude-sonnet-5"
SYSTEM = "You are a probe. Reply with exactly: OK"
USER = "Reply with exactly: OK"

AUTH_MARKERS = ("login", "unauthor", "authenticat", "not logged in", "invalid api key")


def _run(extra_argv, env_overrides, cwd):
    cmd = ["claude", "-p", "--output-format", "json", "--model", MODEL,
           "--system-prompt", SYSTEM] + extra_argv
    env = dict(os.environ)
    env.update(env_overrides)
    try:
        proc = subprocess.run(cmd, input=USER, capture_output=True, text=True,
                              timeout=300, env=env, cwd=cwd)
    except Exception as exc:  # missing binary, timeout
        return {"auth_ok": False, "done": False, "input": None, "note": repr(exc)[:70]}
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-300:]
        is_auth = any(m in tail.lower() for m in AUTH_MARKERS)
        return {"auth_ok": not is_auth, "done": False, "input": None,
                "note": ("AUTH-FAIL " if is_auth else "") + tail[:60]}
    try:
        parsed = json.loads(proc.stdout)
        events = parsed if isinstance(parsed, list) else [parsed]
        event = next(e for e in events if isinstance(e, dict) and e.get("type") == "result")
    except Exception as exc:
        return {"auth_ok": True, "done": False, "input": None, "note": f"parse: {exc}"[:60]}
    u = event.get("usage") or {}
    tot_in = sum(int(u.get(k) or 0) for k in
                 ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return {"auth_ok": not event.get("is_error"),
            "done": "OK" in (event.get("result") or ""),
            "input": tot_in, "note": ""}


def main():
    neutral = tempfile.mkdtemp(prefix="probe-cwd-")
    mincfg = tempfile.mkdtemp(prefix="probe-cfg-")  # empty; learn if auth survives
    mcp_off = ["--strict-mcp-config"]               # candidate: drops all MCP servers
    no_settings = mcp_off + ["--setting-sources", ""]  # candidate: drop skills/settings
    rungs = [
        ("0 baseline",       [],          {},                              None),
        ("1 strict-mcp",     mcp_off,     {},                              None),
        ("2 +neutral-cwd",   mcp_off,     {},                              neutral),
        ("3 +no-settings",   no_settings, {},                              neutral),
        ("4 +isolated-cfg",  no_settings, {"CLAUDE_CONFIG_DIR": mincfg},   neutral),
    ]
    print(f"{'rung':18} {'auth':6} {'done':6} {'input_tokens':>13}  note")
    print("-" * 70)
    for name, argv, env, cwd in rungs:
        r = _run(argv, env, cwd)
        print(f"{name:18} {str(r['auth_ok']):6} {str(r['done']):6} "
              f"{str(r['input']):>13}  {r['note']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the probe and record the table.**

Run: `.venv/bin/python scripts/isolation_probe.py`
Expected: rung 0 shows a large `input_tokens` (the ~439k-class preload); higher rungs drop it. Paste the full table into `docs/superpowers/PROBE-RESULTS-3b.md`.

- [ ] **Step 4: Record the DECISION in `docs/superpowers/PROBE-RESULTS-3b.md`.** State explicitly:
  - **DEFAULT rung** = the lowest `input_tokens` rung with `auth_ok` AND `done` true, plus its exact argv/env.
  - **FALLBACK rung** = the safest (least aggressive) rung with `auth_ok` true — used when the default hits an auth error at runtime.
  - Whether rung 4 (`CLAUDE_CONFIG_DIR`) authenticated; if not, DEFAULT falls to rung 3 and the ephemeral-config-dir helper in Task 2 is dropped (YAGNI).
  - The **auth-error signature** (exit code + stderr markers) that Task 4's `_is_auth_error` will match.

- [ ] **Step 5: Commit**

```bash
git add scripts/isolation_probe.py docs/superpowers/PROBE-RESULTS-3b.md
git commit -m "spike: isolation probe + measured rung table (Task 1, mechanism-check)"
```

---

### Task 2: LeanProfile + build() factory (the deep-module seam)

**Files:**
- Create: `src/crucible/lean.py`
- Test: `tests/test_lean.py` (new)

**Interfaces:**
- Consumes: nothing (pure stdlib).
- Produces:
  - `LeanProfile` frozen dataclass: `strict_mcp: bool = False`, `setting_sources: str | None = None`, `config_dir: Path | None = None`, `cwd: Path | None = None`, `name: str = "ambient"`.
  - `LeanProfile.build() -> tuple[list[str], dict[str, str], str | None]` returning `(argv_extension, env_overrides, cwd_or_None)`.
  - Module constants set from Task 1's decision: `AMBIENT` (all defaults), `DEFAULT_PROFILE` (the chosen rung), `FALLBACK_PROFILE` (the safest auth-ok rung).
  - `make_min_config_dir() -> str` — creates an ephemeral minimal config dir and returns its path (ONLY if Task 1 showed the config-dir rung authenticates; otherwise omit this function and skip its test).

- [ ] **Step 1: Write the failing tests** (`tests/test_lean.py`, new file). Use the exact argv tokens Task 1 validated:

```python
from pathlib import Path

from crucible.lean import AMBIENT, LeanProfile


def test_ambient_profile_adds_nothing():
    argv, env, cwd = AMBIENT.build()
    assert argv == [] and env == {} and cwd is None
    assert AMBIENT.name == "ambient"


def test_strict_mcp_adds_flag():
    argv, env, cwd = LeanProfile(strict_mcp=True, name="strict-mcp").build()
    assert "--strict-mcp-config" in argv
    assert env == {} and cwd is None


def test_setting_sources_and_cwd():
    p = LeanProfile(strict_mcp=True, setting_sources="", cwd=Path("/tmp/x"), name="r3")
    argv, env, cwd = p.build()
    assert argv == ["--strict-mcp-config", "--setting-sources", ""]
    assert cwd == "/tmp/x"


def test_config_dir_becomes_env_override():
    p = LeanProfile(strict_mcp=True, config_dir=Path("/tmp/cfg"), name="r4")
    argv, env, cwd = p.build()
    assert env == {"CLAUDE_CONFIG_DIR": "/tmp/cfg"}
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest -q tests/test_lean.py -v`. Expected: `ModuleNotFoundError: crucible.lean`.

- [ ] **Step 3: Implement `src/crucible/lean.py`** (adjust the token strings and the three profile constants to Task 1's validated decision):

```python
"""Isolation intent for a claude -p subprocess, expressed as a simple interface
over hidden CLI-flag mechanics (deep-module seam). A claude -p call inherits the
operator's whole ~/.claude by default -- MCP tool schemas, skills, CLAUDE.md --
which is pure overhead for a call that only writes a test file (~439k input
tokens per module, gate-7 receipt). A LeanProfile strips that: build() turns
four plain questions into the (argv, env, cwd) the provider passes to the
subprocess. Rungs and tokens are validated by scripts/isolation_probe.py;
docs/superpowers/PROBE-RESULTS-3b.md is the source of truth."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LeanProfile:
    strict_mcp: bool = False
    setting_sources: str | None = None
    config_dir: Path | None = None
    cwd: Path | None = None
    name: str = "ambient"

    def build(self) -> tuple[list[str], dict[str, str], str | None]:
        argv: list[str] = []
        if self.strict_mcp:
            argv.append("--strict-mcp-config")           # PROBE-VALIDATED token
        if self.setting_sources is not None:
            argv += ["--setting-sources", self.setting_sources]
        env: dict[str, str] = {}
        if self.config_dir is not None:
            env["CLAUDE_CONFIG_DIR"] = str(self.config_dir)
        cwd = str(self.cwd) if self.cwd is not None else None
        return argv, env, cwd


# Constants set from Task 1's decision. Example shown assumes the config-dir rung
# authenticates (floor). If it did not, set DEFAULT_PROFILE to the rung-3 shape
# and drop make_min_config_dir + its test.
AMBIENT = LeanProfile(name="ambient")
FALLBACK_PROFILE = LeanProfile(strict_mcp=True, cwd=None, name="strict-mcp")


def make_min_config_dir() -> str:
    """Ephemeral minimal CLAUDE_CONFIG_DIR: only what Task 1 proved auth needs
    (e.g. a copied 0600 credentials file), no MCP, no skills, no CLAUDE.md.
    Cleaned up by the caller. Omit entirely if the config-dir rung failed auth."""
    d = tempfile.mkdtemp(prefix="crucible-leancfg-")
    # If Task 1 showed auth needs a credential file present, copy ONLY that file
    # here (path recorded in PROBE-RESULTS-3b.md). If auth is keychain-borne, the
    # empty dir is sufficient.
    return d


def default_profile() -> LeanProfile:
    """The chosen default rung, built fresh so cwd/config_dir are per-call temp
    dirs. Shape per Task 1's decision."""
    return LeanProfile(
        strict_mcp=True,
        setting_sources="",
        cwd=tempfile.mkdtemp(prefix="crucible-leancwd-"),
        config_dir=Path(make_min_config_dir()),
        name="isolated-cfg",
    )
```

Note: `default_profile()` is a function (not a constant) because it mints fresh temp dirs per call. `os` is imported for Task 3's escape-hatch read; keep it.

- [ ] **Step 4: Run** `tests/test_lean.py` then the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/lean.py tests/test_lean.py
git commit -m "feat: LeanProfile — isolation intent behind a build() seam (rungs per Task 1 probe)"
```

---

### Task 3: Wire LeanProfile into ClaudeCLIProvider + escape hatch

**Files:**
- Modify: `src/crucible/providers_ext.py` (`ClaudeCLIProvider.__init__` and `complete_with_usage`)
- Test: `tests/test_providers_ext.py` (append)

**Interfaces:**
- Consumes: `crucible.lean.{AMBIENT, default_profile}` (Task 2).
- Produces: `ClaudeCLIProvider(run=..., lean_profile=None)`. When `lean_profile is None`, the provider resolves it: `AMBIENT` if `os.environ.get("CRUCIBLE_LEAN") == "0"`, else `default_profile()`. `complete_with_usage` merges the profile's `build()` output into the subprocess: `cmd = [base...] + argv`, `env = {**os.environ, **env_overrides}` passed as `env=`, and `cwd=` set. The provider exposes `self.isolation_name` (the configured profile's `name`) and `self.served_isolation` (updated per call; == `isolation_name` unless Task 4's fallback fires).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_providers_ext.py`):

```python
def test_claude_cli_applies_lean_profile_argv_env_cwd(monkeypatch):
    from crucible.lean import LeanProfile
    from crucible.providers_ext import ClaudeCLIProvider
    calls = {}

    def fake_run(cmd, input=None, capture_output=True, text=True, timeout=None, env=None, cwd=None):
        calls["cmd"], calls["env"], calls["cwd"] = cmd, env, cwd
        return _FakeProc(stdout=_cli_envelope("hi", 10, 2))

    prof = LeanProfile(strict_mcp=True, config_dir=Path("/tmp/cfg"), cwd=Path("/tmp/cwd"),
                       name="r4")
    p = ClaudeCLIProvider(run=fake_run, lean_profile=prof)
    p.complete_with_usage("SYS", "USER", model="claude-sonnet-5")
    assert "--strict-mcp-config" in calls["cmd"]
    assert calls["cwd"] == "/tmp/cwd"
    assert calls["env"]["CLAUDE_CONFIG_DIR"] == "/tmp/cfg"
    assert calls["env"]["PATH"] == os.environ["PATH"]   # ambient env preserved, then overridden
    assert p.isolation_name == "r4" and p.served_isolation == "r4"


def test_claude_cli_escape_hatch_forces_ambient(monkeypatch):
    from crucible.providers_ext import ClaudeCLIProvider
    monkeypatch.setenv("CRUCIBLE_LEAN", "0")
    calls = {}

    def fake_run(cmd, input=None, capture_output=True, text=True, timeout=None, env=None, cwd=None):
        calls["cmd"], calls["cwd"] = cmd, cwd
        return _FakeProc(stdout=_cli_envelope("hi", 10, 2))

    p = ClaudeCLIProvider(run=fake_run)   # no profile -> resolves from env
    p.complete_with_usage("SYS", "USER")
    assert "--strict-mcp-config" not in calls["cmd"]
    assert calls["cwd"] is None
    assert p.isolation_name == "ambient"
```

Add `import os` and `from pathlib import Path` to the test file's imports if absent.

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest -q tests/test_providers_ext.py -k "lean_profile or escape_hatch" -v`. Expected: FAIL (`__init__` takes no `lean_profile`; `env`/`cwd` not passed).

- [ ] **Step 3: Implement.** In `providers_ext.py`, add `import os` at top; extend `ClaudeCLIProvider`:

```python
    def __init__(self, run=subprocess.run, lean_profile=None):
        self._run = run
        if lean_profile is None:
            from crucible.lean import AMBIENT, default_profile
            lean_profile = AMBIENT if os.environ.get("CRUCIBLE_LEAN") == "0" else default_profile()
        self._profile = lean_profile
        self.isolation_name = lean_profile.name
        self.served_isolation = lean_profile.name

    def complete_with_usage(self, system, user, model=None):
        model = model or self.default_model
        argv, env_overrides, cwd = self._profile.build()
        cmd = ["claude", "-p", "--output-format", "json",
               "--model", model, "--system-prompt", system] + argv
        env = {**os.environ, **env_overrides} if env_overrides else None
        try:
            proc = self._run(cmd, input=user, capture_output=True, text=True,
                             timeout=self.request_timeout, env=env, cwd=cwd)
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

Note: the existing test `test_claude_cli_provider_parses_text_and_usage` passes `fake_run` WITHOUT `env`/`cwd` params — update that fake's signature to accept `env=None, cwd=None` (and any other `ClaudeCLIProvider` fake in the file) so the new call site does not break it.

- [ ] **Step 4: Run** the provider tests then the full suite `.venv/bin/python -m pytest -q -W error`. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/providers_ext.py tests/test_providers_ext.py
git commit -m "feat: ClaudeCLIProvider applies LeanProfile (argv/env/cwd) + CRUCIBLE_LEAN=0 escape hatch"
```

---

### Task 4: Bounded auth-class fallback

**Files:**
- Modify: `src/crucible/providers_ext.py` (`_is_auth_error` helper + one retry in `complete_with_usage`)
- Test: `tests/test_providers_ext.py` (append)

**Interfaces:**
- Consumes: `crucible.lean.FALLBACK_PROFILE` (Task 2).
- Produces: on an auth-class failure (exit code + stderr markers per Task 1's recorded signature), when the current profile is not already the fallback, `complete_with_usage` retries EXACTLY ONCE with `FALLBACK_PROFILE`, sets `self.served_isolation = FALLBACK_PROFILE.name`, and prints one loud line. A non-auth error still fails loud. Auth failure even at the fallback fails loud with an actionable message.

- [ ] **Step 1: Write the failing tests** (append):

```python
def test_claude_cli_auth_fallback_retries_once_and_records(capsys):
    from crucible.lean import LeanProfile
    from crucible.providers_ext import ClaudeCLIProvider
    seq = iter([
        _FakeProc(returncode=1, stderr="Error: not logged in (run `claude login`)"),  # floor: auth-fail
        _FakeProc(stdout=_cli_envelope("hi", 10, 2)),                                  # fallback: ok
    ])

    def fake_run(cmd, input=None, capture_output=True, text=True, timeout=None, env=None, cwd=None):
        return next(seq)

    floor = LeanProfile(strict_mcp=True, config_dir=Path("/tmp/cfg"), name="isolated-cfg")
    p = ClaudeCLIProvider(run=fake_run, lean_profile=floor)
    reply, usage = p.complete_with_usage("SYS", "USER")
    assert reply == "hi"
    assert p.served_isolation == "strict-mcp"   # FALLBACK_PROFILE.name
    assert "fallback" in capsys.readouterr().out.lower()


def test_claude_cli_auth_fail_even_at_fallback_raises(capsys):
    from crucible.lean import FALLBACK_PROFILE
    from crucible.providers_ext import ClaudeCLIProvider

    def fake_run(cmd, input=None, capture_output=True, text=True, timeout=None, env=None, cwd=None):
        return _FakeProc(returncode=1, stderr="not logged in")

    p = ClaudeCLIProvider(run=fake_run, lean_profile=FALLBACK_PROFILE)
    with pytest.raises(RuntimeError, match="CRUCIBLE_LEAN=0"):
        p.complete_with_usage("SYS", "USER")


def test_claude_cli_non_auth_error_still_fails_loud():
    from crucible.lean import LeanProfile
    from crucible.providers_ext import ClaudeCLIProvider

    def fake_run(cmd, input=None, capture_output=True, text=True, timeout=None, env=None, cwd=None):
        return _FakeProc(returncode=1, stderr="segfault in model runtime")

    p = ClaudeCLIProvider(run=fake_run, lean_profile=LeanProfile(name="isolated-cfg"))
    with pytest.raises(RuntimeError, match="segfault"):
        p.complete_with_usage("SYS", "USER")
```

- [ ] **Step 2: Run to verify failure** — the floor auth-fail currently raises instead of retrying.

- [ ] **Step 3: Implement.** Add the helper and refactor the call. Add near the top of `providers_ext.py`:

```python
# Auth-class failure signature (Task 1 probe, docs/superpowers/PROBE-RESULTS-3b.md).
_AUTH_MARKERS = ("not logged in", "login", "unauthor", "authenticat", "invalid api key")


def _is_auth_error(returncode: int, stderr: str) -> bool:
    return returncode != 0 and any(m in (stderr or "").lower() for m in _AUTH_MARKERS)
```

Refactor `complete_with_usage` so the subprocess call + parse live in a private `_one_call(system, user, model, profile)` returning `(text, Usage)` and raising on non-zero/malformed (the Task 3 body, minus the profile-resolution). Then:

```python
    def complete_with_usage(self, system, user, model=None):
        from crucible.lean import FALLBACK_PROFILE
        try:
            return self._one_call(system, user, model, self._profile)
        except _AuthError as exc:
            if self._profile.name == FALLBACK_PROFILE.name:
                raise RuntimeError(
                    "claude -p auth failed even at the fallback isolation rung; "
                    "re-run scripts/isolation_probe.py or set CRUCIBLE_LEAN=0"
                ) from exc
            print(f"LEAN FALLBACK: auth failed at rung {self._profile.name!r}, "
                  f"retrying at {FALLBACK_PROFILE.name!r}")
            self.served_isolation = FALLBACK_PROFILE.name
            return self._one_call(system, user, model, FALLBACK_PROFILE)
```

where `_one_call` raises a private `_AuthError(RuntimeError)` when `_is_auth_error(...)` is true (carrying the stderr), and a plain `RuntimeError` otherwise. Define `class _AuthError(RuntimeError): pass` at module level. Keep the existing `is_error` / malformed-envelope / FileNotFoundError paths inside `_one_call` unchanged.

- [ ] **Step 4: Run** the provider tests then the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/providers_ext.py tests/test_providers_ext.py
git commit -m "feat: bounded auth-class fallback to the safest isolation rung (one retry, recorded)"
```

---

### Task 5: Record the isolation rung in meta.json + report

**Files:**
- Modify: `src/crucible/cli.py` (`_cmd_run` meta dict; post-run served-rung patch)
- Modify: `src/crucible/report.py` (`summarize`)
- Test: `tests/test_receipts.py`, `tests/test_report.py` (append)

**Interfaces:**
- Consumes: `getattr(provider, "isolation_name", "ambient")` and `getattr(provider, "served_isolation", ...)` (Tasks 3-4).
- Produces: `meta.json` gains `"lean_isolation"` (configured rung, `"ambient"` default for legacy/non-CLI providers) and, after the run, `"lean_isolation_served"` (the rung actually used; equals `lean_isolation` unless the fallback fired). `summarize(run)` surfaces `"lean_isolation": meta.get("lean_isolation", "ambient")`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_report.py`:

```python
def test_summarize_surfaces_lean_isolation_default_and_value():
    base = {"meta": {"arm": "harden"}, "rounds": [],
            "result": {"verdict": "dry", "total_cost_usd": 0.0, "baseline_survivors": []}}
    assert summarize(base)["lean_isolation"] == "ambient"          # legacy meta
    lean = dict(base, meta={"arm": "harden", "lean_isolation": "isolated-cfg"})
    assert summarize(lean)["lean_isolation"] == "isolated-cfg"
```

Append to `tests/test_receipts.py` (mirror the existing CLI-meta test added in Plan 3a Task 2; a `fake` provider has no `isolation_name`, so it defaults to `"ambient"`):

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
    assert meta["lean_isolation"] == "ambient"          # fake has no isolation_name
    assert meta["lean_isolation_served"] == "ambient"
```

- [ ] **Step 2: Run to verify failure** — `KeyError: 'lean_isolation'`.

- [ ] **Step 3: Implement.** In `cli.py`'s `_cmd_run` meta dict, after the `"tester_billing"`/`"critic_billing"` entries, add:

```python
        "lean_isolation": getattr(tester, "isolation_name", "ambient"),
```

After the loop finishes and before the function returns (where `run_dir` and `tester` are in scope), patch the served rung:

```python
    meta_path = run_dir / "meta.json"
    m = json.loads(meta_path.read_text())
    m["lean_isolation_served"] = getattr(tester, "served_isolation",
                                         m.get("lean_isolation", "ambient"))
    meta_path.write_text(json.dumps(m, indent=2))
```

(If `_cmd_run` uses a single tester/critic and the critic is a distinct CLI provider, prefer the tester's rung for the headline field; both share one config in practice. `json` is already imported in `cli.py`.) In `report.py`'s `summarize`, add to the returned dict:

```python
        "lean_isolation": run["meta"].get("lean_isolation", "ambient"),
```

- [ ] **Step 4: Run the full suite** — `.venv/bin/python -m pytest -q -W error`. Expected: all pass (legacy fixtures default to `"ambient"`).

- [ ] **Step 5: Commit**

```bash
git add src/crucible/cli.py src/crucible/report.py tests/test_receipts.py tests/test_report.py
git commit -m "feat: record lean_isolation rung (configured + served) in meta and summarize"
```

---

### Task 6: Proof run — re-harden guard.py, compare receipt (gate, orchestrator drives)

**Files:** none in this repo (receipts land in rag-guard's `.crucible-runs/`; generated tests on its local branch — discarded after the number is read).

**Interfaces:** consumes the whole chain end to end; produces the apples-to-apples token comparison that closes item 1.

- [ ] **Step 1:** Confirm `feat/lean-invocation` is on `28c58fc`'s lineage and the full suite is green (`.venv/bin/python -m pytest -q -W error` -> 251+ passed). Confirm `docs/superpowers/PROBE-RESULTS-3b.md` records a DEFAULT rung with a real order-of-magnitude token drop at rung 0->default.
- [ ] **Step 2:** On a THROWAWAY branch of rag-guard, run the loop against `rag_guard/guard.py` exactly as the acceptance did (the `harden-tests` skill or `crucible harden ... --tester claude-cli --critic claude-cli`), lean invocation active (default profile; do NOT set `CRUCIBLE_LEAN=0`).
- [ ] **Step 3:** Read the new receipt's per-round `usage_in` (now cache-summed) and `meta.json` `lean_isolation`/`lean_isolation_served`. Verify: total input tokens are an order of magnitude below 439,230 (target `< ~44,000`); guard.py baseline survivors still killed (a real harden); `billing: max-plan`, $0 metered.
- [ ] **Step 4:** Independent reviewer (opus) verifies the receipt numbers against the 439,230 baseline receipt (`~/.crucible-runs/rag-guard/20260712T050833Z-rag-guard-harden`) — same module, same loop, only isolation changed.
- [ ] **Step 5:** Discard the rag-guard throwaway branch (PR is Jeff's separate call). Record the before/after numbers + run dir in the memory file and the wiki build log. Jeff approves the gate by name; item 1 complete.

---

## Self-Review Notes

**Spec coverage:** §2 acceptance -> Task 6; §3 isolation ladder + probe -> Task 1; §4 provider knobs (LeanProfile seam, ephemeral config dir, neutral cwd) -> Tasks 2-3; §5 lean-as-default + escape hatch + bounded fallback -> Tasks 3-4; §6 meta records the rung -> Task 5; §7 testing -> per-task TDD + Task 6 live proof; §8 risks -> Task 1 resolves the auth HIGH, Task 4 the runtime blip; §9 YAGNI (no multi-rung cascade, ephemeral config dir, loop.py/RoundRecord untouched, one meta field) -> respected across Tasks 2-5.

**Probe-first dependency (recorded):** Tasks 2-5 are expressed entirely through the `LeanProfile` seam, so only two things depend on Task 1's live results — the exact argv tokens in `build()` and the field values of `DEFAULT_PROFILE`/`FALLBACK_PROFILE`. Everything else (wiring, escape hatch, fallback, meta) is rung-agnostic. If rung 4 fails auth, `default_profile()` drops `config_dir` and `make_min_config_dir` is deleted (YAGNI); no other task changes.

**Placeholder scan:** none — every code step is complete; the two probe-validated substitution points are called out explicitly, not left vague.

**Type consistency:** `LeanProfile` field names and `.build()` return shape match across Tasks 2/3/4; `isolation_name`/`served_isolation` attrs consistent across Tasks 3/4/5; `lean_isolation`/`lean_isolation_served` meta keys and the `"ambient"` default consistent across Tasks 5's cli/report/tests; `FALLBACK_PROFILE.name` used identically in Task 4's code and tests.

**Base-branch guard (recorded):** this plan MUST build on `28c58fc` (gate-7 fixes: cache-token summing). The gate-7 fixes are not yet in `origin/main` (`f6d058b` squash predates them) — reconciling main is Jeff's call at PR time (recommended: land the gate-7 delta as its own small PR first, then 3b off corrected main).
