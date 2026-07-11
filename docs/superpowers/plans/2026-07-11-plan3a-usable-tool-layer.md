# Plan 3a: Usable-Tool Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make crucible free to run on the Max plan and invocable in one sentence: a `claude -p` provider, a `crucible scope` setup command with a $0 canary probe, and a thin in-repo `harden-tests` skill.

**Architecture:** A new `ClaudeCLIProvider` slots behind the existing `Provider` duck-type (the loop/env/guardrails never change). Billing provenance (`"api"` vs `"max-plan"`) is a provider class attribute recorded in each run's `meta.json` and surfaced by `summarize`. `crucible experiment` refuses any non-`"api"` provider. Scope setup logic is ported from the frozen `experiments/validate_scopes.py` into a first-class `src/crucible/scope.py` with a canary must-kill probe that gates all model spend.

**Tech Stack:** Python 3.11+ stdlib only (subprocess for the CLI provider); pytest; mutmut via the existing engine seam; Claude Code headless (`claude -p`).

**Spec:** `docs/superpowers/specs/2026-07-11-plan3a-usable-tool-layer-design.md`

## Global Constraints

- Stdlib only; no new pip dependencies.
- TDD every task; full suite green under `.venv/bin/python -m pytest -q -W error` at every commit.
- No paid or Max-billed model call in any test (fakes only). The ONE sanctioned live call is Task 1 Step 1's envelope probe and Task 7's acceptance run.
- `loop.py` and `guardrails.py` are untouched. `experiments/` is frozen — nothing under it changes.
- Comments state constraints, not narration. Plain-ASCII CLI output.
- Providers: model ids passed to `claude -p` are FULL ids (e.g. `claude-sonnet-5`) so `crucible.meter` prices them unchanged — the meter needs no edits in this plan.
- Commit messages: conventional, one task's files per commit, `git add` specific paths only.

---

### Task 1: ClaudeCLIProvider (providers_ext.py)

**Files:**
- Modify: `src/crucible/providers_ext.py` (add class + registry entry; add `billing` attrs)
- Test: `tests/test_providers_ext.py` (append)

**Interfaces:**
- Consumes: `oracle_gate.providers.Provider`, `Usage` (existing).
- Produces: class `ClaudeCLIProvider(Provider)` with `name="claude-cli"`, `lineage="anthropic"`, `billing="max-plan"`, `default_model="claude-sonnet-5"`, `request_timeout=1200`, and `complete_with_usage(system, user, model=None) -> tuple[str, Usage]`. Also: `AnthropicProvider`-family and `OpenAIProvider` gain nothing — a module-level convention that ABSENT `billing` attr means `"api"` (Task 2 reads it via `getattr(p, "billing", "api")`). `get_provider("claude-cli")` returns the new class.

- [ ] **Step 1: Live envelope probe (the ONE sanctioned Max-billed call, ~30 tokens).** Run and paste the full JSON into the task notes:

```bash
echo "Reply with exactly: pong" | claude -p --output-format json --model claude-sonnet-5 --system-prompt "You are a test probe." 2>&1
```

Expected shape (verify; adjust Step 2's canned envelope and Step 4's parsing ONLY if the real fields differ — record any difference in the commit message):
`{"type":"result","subtype":"success","is_error":false,"result":"pong","usage":{"input_tokens":N,"output_tokens":N,...},"total_cost_usd":...,"session_id":"..."}`.
If `--system-prompt` is rejected by this CLI version, probe `--append-system-prompt`; whichever works is the flag Step 4 uses.

- [ ] **Step 2: Write the failing tests** (append to `tests/test_providers_ext.py`):

```python
import json as _json


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _cli_envelope(text="pong", inp=12, out=5):
    return _json.dumps({
        "type": "result", "subtype": "success", "is_error": False,
        "result": text, "usage": {"input_tokens": inp, "output_tokens": out},
        "total_cost_usd": 0.0, "session_id": "s",
    })


def test_claude_cli_provider_parses_text_and_usage(monkeypatch):
    from crucible.providers_ext import ClaudeCLIProvider
    calls = {}

    def fake_run(cmd, input=None, capture_output=True, text=True, timeout=None):
        calls["cmd"], calls["input"], calls["timeout"] = cmd, input, timeout
        return _FakeProc(stdout=_cli_envelope("hello", 100, 42))

    p = ClaudeCLIProvider(run=fake_run)
    reply, usage = p.complete_with_usage("SYS", "USER", model="claude-sonnet-5")
    assert reply == "hello"
    assert usage == Usage(100, 42)
    assert calls["cmd"][0] == "claude" and "-p" in calls["cmd"]
    assert "--output-format" in calls["cmd"] and "json" in calls["cmd"]
    assert "claude-sonnet-5" in calls["cmd"]
    assert calls["input"] == "USER"          # user prompt via stdin, never argv
    assert "SYS" in calls["cmd"]             # system prompt via flag
    assert calls["timeout"] == ClaudeCLIProvider.request_timeout == 1200


def test_claude_cli_provider_error_paths(monkeypatch):
    from crucible.providers_ext import ClaudeCLIProvider
    p_exit = ClaudeCLIProvider(run=lambda *a, **k: _FakeProc(returncode=1, stderr="boom"))
    with pytest.raises(RuntimeError, match="boom"):
        p_exit.complete_with_usage("s", "u")
    p_json = ClaudeCLIProvider(run=lambda *a, **k: _FakeProc(stdout="not json"))
    with pytest.raises(RuntimeError, match="envelope"):
        p_json.complete_with_usage("s", "u")

    def raise_fnf(*a, **k):
        raise FileNotFoundError("claude")

    p_missing = ClaudeCLIProvider(run=raise_fnf)
    with pytest.raises(RuntimeError, match="claude"):
        p_missing.complete_with_usage("s", "u")


def test_claude_cli_provider_is_error_envelope_fails_loud():
    from crucible.providers_ext import ClaudeCLIProvider
    env = _json.dumps({"type": "result", "is_error": True, "result": "over quota",
                       "usage": {"input_tokens": 1, "output_tokens": 1}})
    p = ClaudeCLIProvider(run=lambda *a, **k: _FakeProc(stdout=env))
    with pytest.raises(RuntimeError, match="over quota"):
        p.complete_with_usage("s", "u")


def test_billing_attrs():
    from crucible.providers_ext import ClaudeCLIProvider
    assert ClaudeCLIProvider.billing == "max-plan"
    # absent attr means "api" -- the convention Task 2's meta stamping reads
    assert getattr(LongAnthropicProvider, "billing", "api") == "api"
    assert getattr(get_provider("openai"), "billing", "api") == "api"


def test_registry_has_claude_cli():
    from crucible.providers_ext import ClaudeCLIProvider
    assert get_provider("claude-cli").__class__ is ClaudeCLIProvider
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_providers_ext.py -k "claude_cli or billing or registry_has" -v`
Expected: FAIL with `ImportError: cannot import name 'ClaudeCLIProvider'`

- [ ] **Step 4: Implement** (append to `src/crucible/providers_ext.py`; add `import subprocess` and `import json` at top):

```python
class ClaudeCLIProvider(Provider):
    """Model calls via `claude -p` headless: bills the operator's Claude
    subscription (Max plan), not the metered API. billing="max-plan" marks
    every receipt so plan-covered shadow dollars are never mistaken for an
    invoice. No output_cap exists (the CLI takes no max_tokens), so env._call's
    mechanical truncation check is structurally silent here -- the v9
    amendment's detection asymmetry, accepted and disclosed, not skipped
    silently. User prompt goes via stdin (argv has length limits; module
    sources do not)."""

    name = "claude-cli"
    lineage = "anthropic"
    billing = "max-plan"
    default_model = "claude-sonnet-5"
    request_timeout = 1200

    def __init__(self, run=subprocess.run):
        self._run = run

    def complete_with_usage(self, system, user, model=None):
        model = model or self.default_model
        cmd = ["claude", "-p", "--output-format", "json",
               "--model", model, "--system-prompt", system]
        try:
            proc = self._run(cmd, input=user, capture_output=True, text=True,
                             timeout=self.request_timeout)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "claude CLI not found on PATH; install Claude Code or use an API provider"
            ) from exc
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p exited {proc.returncode}: {(proc.stderr or '')[-800:]}")
        try:
            data = json.loads(proc.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError(
                f"claude -p returned a malformed envelope: {proc.stdout[-400:]!r}") from exc
        if data.get("is_error"):
            raise RuntimeError(f"claude -p reported an error: {data.get('result', '')[:800]}")
        u = data.get("usage") or {}
        usage = Usage(int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0))
        return data.get("result", ""), usage
```

Registry: add `"claude-cli": ClaudeCLIProvider,` to `get_provider`'s dict.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_providers_ext.py -v` then the full suite `.venv/bin/python -m pytest -q -W error`
Expected: all PASS, no warnings.

- [ ] **Step 6: Commit**

```bash
git add src/crucible/providers_ext.py tests/test_providers_ext.py
git commit -m "feat: ClaudeCLIProvider — claude -p headless behind the Provider seam (billing=max-plan)"
```

---

### Task 2: Billing provenance in receipts + summarize

**Files:**
- Modify: `src/crucible/cli.py` (meta dict in `_cmd_run`)
- Modify: `src/crucible/experiment.py` (meta dict in `run_arm` — find the `ReceiptWriter(` call and its meta dict)
- Modify: `src/crucible/report.py` (`summarize`)
- Test: `tests/test_receipts.py`, `tests/test_report.py` (append)

**Interfaces:**
- Consumes: `getattr(provider, "billing", "api")` convention from Task 1.
- Produces: every new `meta.json` carries `"tester_billing"` and `"critic_billing"` (strings, `"api"` default). `summarize(run)` output dict gains `"billing"`: `"api"` when both roles are `"api"` or keys absent (legacy receipts), else `"max-plan"` when any role is `"max-plan"`, else `"mixed"` reserved by construction (`f"mixed:{t}+{c}"` never arises today but the code handles unequal non-api values by joining them). Exact rule (copy verbatim into implementation): `t = meta.get("tester_billing", "api"); c = meta.get("critic_billing", "api"); billing = t if t == c else f"mixed:{t}+{c}"`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_report.py`:

```python
def test_summarize_billing_field_legacy_default_and_max_plan():
    base = {"meta": {"arm": "harden"}, "rounds": [],
            "result": {"verdict": "dry", "total_cost_usd": 0.0, "baseline_survivors": []}}
    assert summarize(base)["billing"] == "api"          # legacy meta: absent keys
    both = dict(base, meta={"arm": "harden", "tester_billing": "max-plan",
                             "critic_billing": "max-plan"})
    assert summarize(both)["billing"] == "max-plan"
    mixed = dict(base, meta={"arm": "harden", "tester_billing": "api",
                              "critic_billing": "max-plan"})
    assert summarize(mixed)["billing"] == "mixed:api+max-plan"
```

Append to `tests/test_receipts.py` (this tests the CLI meta path; use the existing fake-provider CLI test pattern — see `tests/test_cli.py` for how `_cmd_run` is exercised with `--tester fake`; if no such test exists there, drive `cli.main` directly):

```python
def test_cli_meta_records_billing(tmp_path, subject_clone):
    # subject_clone: reuse the existing fixture that yields a committed git clone
    # with the tiny fixture package (see tests/test_cli.py); if it is named
    # differently there, use that name here.
    import json
    from crucible import cli
    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps(["```python\ndef test_x():\n    assert True\n```"]))
    rc = cli.main(["oneshot", str(subject_clone), "--module", "subject_pkg/calc.py",
                   "--tester", "fake", "--fake-replies", str(replies),
                   "--runs-dir", str(tmp_path / "runs")])
    run_dir = next((tmp_path / "runs").iterdir())
    meta = json.loads((run_dir / "meta.json").read_text())
    assert meta["tester_billing"] == "api"   # FakeProvider has no billing attr
    assert meta["critic_billing"] == "api"
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest -q tests/test_report.py tests/test_receipts.py -k billing -v`. Expected: FAIL (`KeyError: 'billing'` / missing meta keys).

- [ ] **Step 3: Implement.** In `cli.py`'s `_cmd_run` meta dict, after the `"critic_provider"` entry add:

```python
        "tester_billing": getattr(tester, "billing", "api"),
        "critic_billing": getattr(critic, "billing", "api"),
```

In `experiment.py`'s `run_arm`, add the same two keys to its meta dict, reading from the constructed tester/critic provider objects (they exist in scope where the writer is built; if they are named differently, e.g. `tester_p`, use those names). In `report.py`'s `summarize`, add to the returned dict:

```python
        "billing": (lambda t, c: t if t == c else f"mixed:{t}+{c}")(
            run["meta"].get("tester_billing", "api"),
            run["meta"].get("critic_billing", "api")),
```

- [ ] **Step 4: Run the full suite** — `.venv/bin/python -m pytest -q -W error`. Expected: all pass (legacy fixtures default to `"api"`).

- [ ] **Step 5: Commit**

```bash
git add src/crucible/cli.py src/crucible/experiment.py src/crucible/report.py tests/test_report.py tests/test_receipts.py
git commit -m "feat: billing provenance (api vs max-plan) in run meta and summarize"
```

---

### Task 3: Protocol guardrail — experiment refuses non-API providers

**Files:**
- Modify: `src/crucible/experiment.py` (in `run_arm`, immediately after providers are constructed and before any `ReceiptWriter`/model work)
- Test: `tests/test_experiment.py` (append)

**Interfaces:**
- Consumes: `getattr(provider, "billing", "api")`.
- Produces: `run_arm` raises `ValueError` naming the offending provider before any receipt dir is created, whenever tester or critic billing != `"api"`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_experiment.py`, following its existing fixture style for a minimal protocol dict):

```python
def test_run_arm_refuses_non_api_provider(monkeypatch, tmp_path):
    """Pre-registered runs demand metered, receipt-exact spend; a plan-covered
    provider must be refused BEFORE any run dir exists (spec 2026-07-11 §5)."""
    import crucible.experiment as exp

    class MaxPlanFake:
        billing = "max-plan"
        name = "claude-cli"

        def complete_with_usage(self, *a, **k):
            raise AssertionError("must never be called")

    monkeypatch.setattr(exp, "get_provider", lambda name: MaxPlanFake())
    protocol = {  # copy the minimal valid protocol shape used by this file's other tests
        "protocol_version": 1,
        "tester": {"provider": "claude-cli", "model": "claude-sonnet-5"},
        "rounds": {"max_rounds": 1, "dry_rounds": 1},
        "arms": {"oneshot": {"mode": "oneshot"}},
        "subjects": {},
    }
    with pytest.raises(ValueError, match="max-plan"):
        exp.run_arm(protocol, "oneshot", str(tmp_path / "subj"), str(tmp_path / "runs"), "m.py")
    assert not (tmp_path / "runs").exists() or not any((tmp_path / "runs").iterdir())
```

(If `run_arm`'s signature or the protocol fixture shape differs, mirror the file's existing passing tests — the assertion contract is what matters: refusal by `billing`, before any run dir.)

- [ ] **Step 2: Run to verify failure** — expected: the fake provider's `AssertionError` or a crash past the intended refusal point.

- [ ] **Step 3: Implement.** In `run_arm`, right after both providers are constructed:

```python
    for role, prov in (("tester", tester_provider), ("critic", critic_provider)):
        b = getattr(prov, "billing", "api")
        if b != "api":
            raise ValueError(
                f"experiment refuses {role} provider {getattr(prov, 'name', prov)!r}: "
                f"billing={b!r} -- pre-registered runs require metered API spend "
                "(spec docs/superpowers/specs/2026-07-11-plan3a-usable-tool-layer-design.md §5)")
```

(Use the actual local variable names for the providers in `run_arm`; if only the critic is optional in oneshot mode, guard accordingly.)

- [ ] **Step 4: Run the full suite** — all pass.
- [ ] **Step 5: Commit**

```bash
git add src/crucible/experiment.py tests/test_experiment.py
git commit -m "feat: experiment guardrail — refuse non-API (max-plan) providers pre-call"
```

---

### Task 4: scope.py — layout detection + scope write

**Files:**
- Create: `src/crucible/scope.py`
- Test: `tests/test_scope.py` (new)

**Interfaces:**
- Consumes: `crucible.engine.write_scope` (existing signature: `write_scope(pyproject_path, source_paths, also_copy=None, pytest_args=None, create_if_missing=False)`).
- Produces:
  - `detect(subject_dir: Path, module: str) -> ScopePlan` where `ScopePlan` is a frozen dataclass: `module: str`, `also_copy: list[str]`, `pytest_args: list[str]` (exclude-form `--ignore=...` only), `needs_src_shim: bool`, `notes: list[str]`.
  - `apply(subject_dir: Path, plan: ScopePlan) -> None` — writes `[tool.mutmut]` via `write_scope(create_if_missing=True)` and, when `needs_src_shim`, writes the root `conftest.py` sys.path shim (exact v7 content below).
- Detection rules (all mechanical, no guessing):
  - `also_copy`: the top-level directory containing the module (`src` if module starts with `src/`, else the module's first path segment when it is a package dir).
  - `needs_src_shim`: true iff module path starts with `src/` (mutmut trampoline rejects `src.`-qualified imports — v7 lesson).
  - `pytest_args`: for every `tests/test_*.py` whose top-level `import X` / `from X import` names a LOCAL top-level package that is NOT inside `also_copy` and not an installed module (`importlib.util.find_spec` returns None), emit `--ignore=tests/<file>` (v6 lesson, mechanized). Never an include-list.
  - Anything undetectable appends a human-readable line to `notes`; `detect` never raises for heuristics, only for a missing module file (`FileNotFoundError`).

- [ ] **Step 1: Write the failing tests** (`tests/test_scope.py`, new file):

```python
from pathlib import Path

import pytest

from crucible.scope import ScopePlan, apply, detect

SHIM = 'import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))\n'


def _mk(tmp_path, files):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return tmp_path


def test_detect_package_dir_layout(tmp_path):
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n", "tests/test_mod.py": "import mypkg\n"})
    plan = detect(repo, "mypkg/mod.py")
    assert plan.also_copy == ["mypkg"]
    assert plan.needs_src_shim is False
    assert plan.pytest_args == []


def test_detect_src_layout_needs_shim(tmp_path):
    repo = _mk(tmp_path, {"src/mod.py": "X = 1\n"})
    plan = detect(repo, "src/mod.py")
    assert plan.also_copy == ["src"]
    assert plan.needs_src_shim is True


def test_detect_flags_sandbox_hazard_test_files(tmp_path):
    repo = _mk(tmp_path, {
        "mypkg/mod.py": "X = 1\n",
        "tests/test_ok.py": "import mypkg\n",
        "tests/test_hazard.py": "from toolbelt import helper\n",  # local pkg outside also_copy
        "toolbelt/__init__.py": "helper = 1\n",
    })
    plan = detect(repo, "mypkg/mod.py")
    assert plan.pytest_args == ["--ignore=tests/test_hazard.py"]


def test_detect_missing_module_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        detect(tmp_path, "nope/missing.py")


def test_apply_writes_scope_and_shim(tmp_path):
    repo = _mk(tmp_path, {"src/mod.py": "X = 1\n"})
    apply(repo, detect(repo, "src/mod.py"))
    py = (repo / "pyproject.toml").read_text()
    assert 'source_paths = ["src/mod.py"]' in py
    assert 'also_copy = ["src"]' in py
    assert (repo / "conftest.py").read_text() == SHIM
```

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError: crucible.scope`.

- [ ] **Step 3: Implement `src/crucible/scope.py`:**

```python
"""Scope setup for a subject repo: detect layout, write [tool.mutmut], flag
sandbox-hazard test files. Mechanizes the lessons the experiment learned the
hard way: exclude-form pytest_args only (v6 -- an include-list silently
stops collecting freshly generated tests), a src-layout conftest shim (v7 --
mutmut's trampoline rejects src.-qualified imports). Heuristics never guess:
what detect() cannot prove lands in notes, and the canary probe (crucible
scope's second half) is the mechanical gate before any model spend."""
from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

from crucible.engine import write_scope

SRC_SHIM = 'import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))\n'


@dataclass(frozen=True)
class ScopePlan:
    module: str
    also_copy: list[str]
    pytest_args: list[str]
    needs_src_shim: bool
    notes: list[str] = field(default_factory=list)


def _top_level_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def detect(subject_dir: Path, module: str) -> ScopePlan:
    subject_dir = Path(subject_dir)
    if not (subject_dir / module).is_file():
        raise FileNotFoundError(f"module not found in subject: {module}")
    top = Path(module).parts[0]
    also_copy = [top]
    needs_src_shim = top == "src"
    notes: list[str] = []
    pytest_args: list[str] = []
    tests_dir = subject_dir / "tests"
    if tests_dir.is_dir():
        for tf in sorted(tests_dir.glob("test_*.py")):
            hazards = {
                name for name in _top_level_imports(tf)
                if name != top
                and (subject_dir / name).is_dir()               # local top-level package...
                and importlib.util.find_spec(name) is None      # ...not an installed one
            }
            if hazards:
                pytest_args.append(f"--ignore=tests/{tf.name}")
                notes.append(f"tests/{tf.name} imports local package(s) "
                             f"{sorted(hazards)} absent from mutmut's sandbox")
    return ScopePlan(module=module, also_copy=also_copy, pytest_args=pytest_args,
                     needs_src_shim=needs_src_shim, notes=notes)


def apply(subject_dir: Path, plan: ScopePlan) -> None:
    subject_dir = Path(subject_dir)
    if plan.needs_src_shim:
        (subject_dir / "conftest.py").write_text(SRC_SHIM)
    write_scope(subject_dir / "pyproject.toml", [plan.module],
                also_copy=plan.also_copy,
                pytest_args=plan.pytest_args or None,
                create_if_missing=True)
```

- [ ] **Step 4: Run** `tests/test_scope.py` then the full suite. Expected: all pass.
- [ ] **Step 5: Commit**

```bash
git add src/crucible/scope.py tests/test_scope.py
git commit -m "feat: crucible.scope — mechanical layout detection + scope write (v6/v7 lessons mechanized)"
```

---

### Task 5: Canary probe + `crucible scope` subcommand

**Files:**
- Modify: `src/crucible/scope.py` (add `canary_probe`)
- Modify: `src/crucible/cli.py` (add `scope` subparser + `_cmd_scope`)
- Test: `tests/test_scope.py` (append; one `@pytest.mark.slow` real-mutmut test), `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `crucible.engine.MutmutEngine` (existing: `MutmutEngine(cwd, run=...).measure() -> MutationOutcome` with `.counts["killed"]`, `.all_mutants`).
- Produces: `canary_probe(subject_dir: Path, module: str, run=subprocess.run) -> CanaryVerdict` — frozen dataclass `CanaryVerdict(kills_before: int, kills_after: int, mutants: int, passed: bool)`; `passed` iff `kills_after > kills_before`. CLI: `crucible scope <subject> --module <M>` — runs `detect`+`apply`+`canary_probe`, prints a plain summary, exit 0 on pass / 4 on canary failure. The canary test content: import the module by its mutmut-visible name and call/touch one public symbol, generated as:

```python
CANARY = (
    "import importlib\n"
    "mod = importlib.import_module({modname!r})\n"
    "def test_crucible_canary():\n"
    "    names = [n for n in dir(mod) if not n.startswith('_')]\n"
    "    assert names, 'module exports nothing public'\n"
    "    assert getattr(mod, names[0]) is not None\n"
)
```

where `modname` is the module path minus `.py`, dots for slashes, with a leading `src.` stripped when the shim is in play (v7: bare name, never `src.`-qualified). File written to `tests/crucible_canary_test.py`, always deleted in a `finally`.

**Key honesty note copied into the docstring:** a `dir()`-based canary proves COLLECTION (the v6 failure class: the file must be collected and its assertion executed for any mutant to be attributed), which is the gate's purpose; it does not prove deep behavioral coverage — the loop's generated tests do that.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_scope.py`:

```python
def test_canary_probe_passes_when_kills_increase(tmp_path, monkeypatch):
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, killed):
            self.counts = {"killed": killed}
            self.all_mutants = 10
            self.survivors = []

    measures = iter([FakeOutcome(3), FakeOutcome(5)])

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return next(measures)

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n", "tests/__init__.py": ""})

    # pristine canary check subprocess: exit 0
    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        class P:
            returncode, stdout, stderr = 0, "1 passed", ""
        return P()

    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)
    assert v.passed is True and (v.kills_before, v.kills_after) == (3, 5)
    assert not (repo / "tests" / "crucible_canary_test.py").exists()  # cleaned up


def test_canary_probe_fails_when_kills_flat(tmp_path, monkeypatch):
    import crucible.scope as scope_mod

    class FakeOutcome:
        def __init__(self, killed):
            self.counts = {"killed": killed}
            self.all_mutants = 10
            self.survivors = []

    measures = iter([FakeOutcome(3), FakeOutcome(3)])

    class FakeEngine:
        def __init__(self, cwd, run=None):
            pass

        def measure(self):
            return next(measures)

    monkeypatch.setattr(scope_mod, "MutmutEngine", FakeEngine)
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        class P:
            returncode, stdout, stderr = 0, "1 passed", ""
        return P()

    v = scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)
    assert v.passed is False


def test_canary_probe_refuses_pristine_failing_canary(tmp_path, monkeypatch):
    import crucible.scope as scope_mod
    repo = _mk(tmp_path, {"mypkg/mod.py": "X = 1\n"})

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=None, **kw):
        class P:
            returncode, stdout, stderr = 1, "1 failed", "boom"
        return P()

    with pytest.raises(RuntimeError, match="canary failed on pristine"):
        scope_mod.canary_probe(repo, "mypkg/mod.py", run=fake_run)


@pytest.mark.slow
def test_canary_probe_real_mutmut_on_fixture_subject(subject_clone):
    """End-to-end: the same fixture mini-repo the engine's slow tests use.
    Reuse the existing committed-clone fixture from tests/test_cli.py or
    tests/test_env.py (whichever provides subject_clone); apply scope, then
    the canary must strictly increase kills."""
    from crucible.scope import apply, canary_probe, detect
    apply(subject_clone, detect(subject_clone, "subject_pkg/calc.py"))
    v = canary_probe(subject_clone, "subject_pkg/calc.py")
    assert v.passed is True
```

Append to `tests/test_cli.py`:

```python
def test_cli_scope_subcommand(monkeypatch, tmp_path, capsys):
    from crucible import cli
    import crucible.scope as scope_mod
    calls = {}
    monkeypatch.setattr(scope_mod, "detect",
                        lambda s, m: scope_mod.ScopePlan(m, ["mypkg"], [], False, []))
    monkeypatch.setattr(scope_mod, "apply", lambda s, p: calls.setdefault("applied", p))
    monkeypatch.setattr(scope_mod, "canary_probe",
                        lambda s, m, run=None: scope_mod.CanaryVerdict(3, 5, 10, True))
    (tmp_path / "mypkg").mkdir(parents=True)
    (tmp_path / "mypkg" / "mod.py").write_text("X = 1\n")
    rc = cli.main(["scope", str(tmp_path), "--module", "mypkg/mod.py"])
    out = capsys.readouterr().out
    assert rc == 0 and "canary" in out.lower() and "3 -> 5" in out


def test_cli_scope_subcommand_canary_failure_exits_4(monkeypatch, tmp_path):
    from crucible import cli
    import crucible.scope as scope_mod
    monkeypatch.setattr(scope_mod, "detect",
                        lambda s, m: scope_mod.ScopePlan(m, ["mypkg"], [], False, []))
    monkeypatch.setattr(scope_mod, "apply", lambda s, p: None)
    monkeypatch.setattr(scope_mod, "canary_probe",
                        lambda s, m, run=None: scope_mod.CanaryVerdict(3, 3, 10, False))
    (tmp_path / "mypkg").mkdir(parents=True)
    (tmp_path / "mypkg" / "mod.py").write_text("X = 1\n")
    rc = cli.main(["scope", str(tmp_path), "--module", "mypkg/mod.py"])
    assert rc == 4
```

- [ ] **Step 2: Run to verify failure** — missing `canary_probe`/`CanaryVerdict`/subcommand.

- [ ] **Step 3: Implement.** Append to `src/crucible/scope.py` (add imports: `subprocess`, `sys`, and `from crucible.engine import MutmutEngine`):

```python
@dataclass(frozen=True)
class CanaryVerdict:
    kills_before: int
    kills_after: int
    mutants: int
    passed: bool


_CANARY = (
    "import importlib\n"
    "mod = importlib.import_module({modname!r})\n"
    "def test_crucible_canary():\n"
    "    names = [n for n in dir(mod) if not n.startswith('_')]\n"
    "    assert names, 'module exports nothing public'\n"
    "    assert getattr(mod, names[0]) is not None\n"
)


def canary_probe(subject_dir: Path, module: str, run=subprocess.run) -> CanaryVerdict:
    """Must-kill collection proof before any model spend (v6 lesson): measure,
    write a canary test, prove it passes pristine, measure again, and require
    the killed count to STRICTLY increase. Proves mutmut actually collects a
    freshly written test file under this scope; does not claim behavioral
    depth -- the loop's generated tests supply that. The canary file is
    removed in a finally, pass or fail."""
    subject_dir = Path(subject_dir)
    modname = module[:-3].replace("/", ".")
    if modname.startswith("src."):
        modname = modname[len("src."):]          # v7: bare name, never src.-qualified
    engine = MutmutEngine(subject_dir, run=run)
    before = engine.measure()
    tests_dir = subject_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    canary = tests_dir / "crucible_canary_test.py"
    try:
        canary.write_text(_CANARY.format(modname=modname))
        pristine = run([sys.executable, "-m", "pytest", "-q", str(canary), "--ignore=mutants"],
                       cwd=str(subject_dir), capture_output=True, text=True, timeout=300)
        if pristine.returncode != 0:
            raise RuntimeError(
                "canary failed on pristine code -- the probe is wrong, not the subject: "
                f"{(pristine.stdout or '')[-400:]}")
        after = engine.measure()
    finally:
        canary.unlink(missing_ok=True)
    return CanaryVerdict(
        kills_before=int(before.counts.get("killed", 0)),
        kills_after=int(after.counts.get("killed", 0)),
        mutants=after.all_mutants,
        passed=int(after.counts.get("killed", 0)) > int(before.counts.get("killed", 0)),
    )
```

In `cli.py`, add the subparser (after the `experiment` one):

```python
    sp = sub.add_parser("scope")
    sp.add_argument("subject")
    sp.add_argument("--module", required=True)
```

and the dispatch branch (before the final `return _cmd_run(...)`):

```python
    if args.cmd == "scope":
        import crucible.scope as scope_mod
        subject = Path(args.subject).resolve()
        plan = scope_mod.detect(subject, args.module)
        scope_mod.apply(subject, plan)
        for note in plan.notes:
            print(f"note: {note}")
        v = scope_mod.canary_probe(subject, args.module)
        status = "KILLS" if v.passed else "NO-KILLS"
        print(f"scope written: also_copy={plan.also_copy} pytest_args={plan.pytest_args} "
              f"shim={plan.needs_src_shim}")
        print(f"canary: {status} ({v.kills_before} -> {v.kills_after} of {v.mutants} mutants)")
        if not v.passed:
            print("REFUSING: a fresh test file is not being collected under this scope; "
                  "fix the scope before spending any model tokens")
            return 4
        return 0
```

- [ ] **Step 4: Run** fast suite, then `.venv/bin/python -m pytest -q -m slow`. Expected: all pass.
- [ ] **Step 5: Commit**

```bash
git add src/crucible/scope.py src/crucible/cli.py tests/test_scope.py tests/test_cli.py
git commit -m "feat: canary must-kill probe + crucible scope subcommand (exit 4 = unproven scope)"
```

---

### Task 6: harden-tests skill (in-repo) + personal symlink

**Files:**
- Create: `.claude/skills/harden-tests/SKILL.md`
- Command (not committed): `ln -s ~/ai-agentic-code-testing/.claude/skills/harden-tests ~/.claude/skills/harden-tests`

**Interfaces:**
- Consumes: `crucible scope` (Task 5 exit codes: 0 pass / 4 canary refusal), `crucible harden --tester claude-cli --critic claude-cli` (Task 1 registry name), receipt summary fields incl. `billing` (Task 2).
- Produces: the invocable skill. No unit tests (reviewed prose; the CLI underneath is tested); opus reviewer reads it as part of the task review.

- [ ] **Step 1: Write `.claude/skills/harden-tests/SKILL.md`:**

```markdown
---
name: harden-tests
description: Use when Jeff asks to "harden tests" for a module/repo -- runs crucible's adversarial test-hardening loop (Tester -> mutation testing -> Critic on named survivors) on the Max plan at $0 metered, onto a LOCAL branch, with mutation-kill receipts. Triggers: "harden tests", "harden the tests for X", "run crucible on X", "mutation-harden".
---

# harden-tests

Runs crucible's adversarial test-hardening loop against one module of the
current repo. Verdicts are mechanical (pytest kills the mutant or it
survives); receipts land in a run directory; generated tests land on a local
branch. Model calls go through `claude -p` on the Max plan: $0 metered,
receipts shadow-priced and flagged `billing: max-plan`.

## Hard guardrails (non-negotiable)

- LOCAL branch only. Never commit to main. Opening a PR is strictly opt-in
  (ask; never assume).
- Only on repos the operator owns or explicitly names. Never mutate the
  upstream: crucible runs in the working clone, add-only for tests.
- If the canary probe refuses (exit 4), STOP and report -- never hand-tune
  the scope to force a pass; a scope the canary cannot prove is a scope that
  silently loses kills (the v6 lesson this gate exists for).
- Requires: `claude` CLI on PATH (logged in), crucible's venv
  (`~/ai-agentic-code-testing/.venv`), a git-clean subject repo.

## Procedure

1. Preflight: confirm the target module path exists; `git status` clean
   enough (crucible's own preflight enforces committed-clean and green
   suite); confirm `.venv` and pytest exist in the subject or use crucible's.
2. Branch: `git checkout -b crucible/harden-<module-stem>-<YYYYMMDD>` (never
   reuse an existing branch).
3. Scope + canary (free, no model calls):
   `~/ai-agentic-code-testing/.venv/bin/crucible scope <repo> --module <M>`
   -- exit 4 means stop and report the printed reason.
4. Run the loop on the Max plan:
   `~/ai-agentic-code-testing/.venv/bin/crucible harden <repo> --module <M>
   --tester claude-cli --critic claude-cli --runs-dir <repo>/.crucible-runs`
5. Commit the accepted `tests/crucible_*_test.py` files to the local branch
   with a message naming kills and the receipt dir.
6. Report, plain ASCII: verdict, kills/baseline survivors, rounds, dropped
   wrong-oracle tests, token totals, shadow cost with the `max-plan` flag
   stated in words ("plan-covered, no metered spend"), receipt path. Offer
   -- do not open -- a PR.

## Refusals

- Dirty repo, missing module, canary exit 4, or `claude` CLI absent: report
  the exact blocker and stop. Never work around a refusal silently.
```

- [ ] **Step 2: Create the symlink and verify the skill loads:**

```bash
ln -sfn ~/ai-agentic-code-testing/.claude/skills/harden-tests ~/.claude/skills/harden-tests
ls -l ~/.claude/skills/harden-tests/SKILL.md
```

Expected: symlink resolves to the repo file.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/harden-tests/SKILL.md
git commit -m "feat: harden-tests skill — one-sentence invocation of the loop on the Max plan"
```

---

### Task 7: Acceptance run (gate 6 — Jeff watches, orchestrator drives)

**Files:** none in this repo (receipts land in the target repo's `.crucible-runs/`; generated tests on its local branch).

**Interfaces:** consumes everything above, end to end.

- [ ] **Step 1:** Jeff names the portfolio repo + module (default offer: `rag-guard`'s `rag_guard/guard.py` — known-good scope shape from the experiment).
- [ ] **Step 2:** Invoke the skill in a Claude Code session exactly as a user would ("harden tests for <module>") and follow its procedure verbatim — any deviation the skill's prose forces is a skill bug to fix before sign-off.
- [ ] **Step 3:** Verify, from the receipt: `tester_billing == critic_billing == "max-plan"`, token counts nonzero, verdict in (clean/dry/cap), kills > 0 OR an honest canary/loop refusal correctly reported.
- [ ] **Step 4:** Confirm $0 metered: no new usage on the Anthropic API console for the run window (Jeff eyeballs; the billing flag is the receipt-side proof).
- [ ] **Step 5:** Jeff approves gate 6 by name. Record the run dir + verdict in the memory file and wiki build log; plan complete.

---

## Self-Review Notes

**Spec coverage:** §3 provider → Task 1; §4 billing/shadow-price → Task 2 (meter unchanged: full model ids price via the existing table — spec §4's "maps to API rates" satisfied with zero code, recorded here); §5 guardrail → Task 3; §6 scope+canary → Tasks 4-5; §7 skill → Task 6; §2 acceptance → Task 7; §10 YAGNI cuts respected (no streaming/session reuse/auto-PR/meter edits/new receipt schema).
**Spec deviation (recorded, one line):** the spec's §4 sentence "env stamps it into each round's record" is implemented at run level (`meta.json` tester_billing/critic_billing) instead of per-round — a run's role→provider mapping is constant, and this keeps `loop.py` untouched as the spec's own artifacts block promises. Spec file amended in the same commit as this plan.
**Placeholder scan:** none — every code step is complete; Task 3's "mirror the file's existing fixtures" names the file and the exact assertion contract.
**Type consistency:** `ScopePlan`/`CanaryVerdict` field names match across Tasks 4/5/6; `billing` values `"api"`/`"max-plan"` and registry name `"claude-cli"` consistent across Tasks 1/2/3/6; exit code 4 consistent between Task 5 CLI and Task 6 skill prose.
