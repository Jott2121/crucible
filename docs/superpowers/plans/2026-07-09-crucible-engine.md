# Crucible Engine Implementation Plan (Plan 1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the crucible adversarial test-hardening engine: a library + CLI where a Tester agent writes tests, mutmut finds survivors, a Critic agent attacks the named survivors, and the loop runs until dry — all verdicts mechanical, all spend metered, all rounds receipted.

**Architecture:** Pure-core / injected-IO (same pattern as oracle-gate): `loop.py` is pure control flow over an injected `Env`; all subprocess/network/filesystem lives in adapters (`engine.py`, `runner.py`, providers). oracle-gate is a hard dependency (providers, survivor parsing, provenance) — never rebuilt. Plan 2 (experiment: related-work sweep, PROTOCOL.md, pilot, runs) and Plan 3 (skill wrapper, public flip) follow once this engine works.

**Tech Stack:** Python >=3.11, mutmut>=3,<4, pytest>=8, oracle-gate (git dep, `tool/` subdirectory), agent-cost-attribution (git dep). Runtime code stdlib-only beyond those.

## Global Constraints

- Python `>=3.11`. mutmut pinned `>=3,<4` (oracle-gate's verified output format).
- Runtime dependencies: exactly `oracle-gate`, `agent-cost-attribution`, `mutmut` — nothing else. Dev extras: `pytest>=8`.
- src layout: all engine code under `src/crucible/`; package name `crucible`; console script `crucible`.
- Every generated test file is named `crucible_<slug>_test.py` — the `crucible_` prefix is load-bearing (guardrail G-ADD asserts nothing else changed).
- Unit tests never touch the network. The only tests that shell out to mutmut are marked `slow`. Real-API tests are marked `integration` and never run in CI.
- Work on branch `feat/engine` in `~/ai-agentic-code-testing`; oracle-gate change on branch `feat/usage-reporting` in `~/oracle-gate` (public repo — clean commit messages).
- Commit at the end of every task (Jeff has approved commits for this build).
- Subject repos are prepared as local clones; crucible never pushes to or mutates an upstream.
- No naive mutation-score thresholds anywhere; scores reported with full denominators (spec §1b/§8).

---

### Task 1: Repo scaffold, packaging, oracle-gate dependency proof

**Files:**
- Create: `pyproject.toml`
- Create: `src/crucible/__init__.py`
- Create: `tests/__init__.py` (empty), `tests/test_packaging.py`
- Create: `.gitignore`

**Interfaces:**
- Consumes: oracle-gate from GitHub (`tool/` subdirectory), agent-cost-attribution from GitHub.
- Produces: importable `crucible` package; `oracle_gate` and `agent_cost_attribution` importable in the venv. Later tasks assume the venv at `.venv/` with `pip install -e ".[dev]"` done.

- [ ] **Step 1: Branch and scaffold**

```bash
cd ~/ai-agentic-code-testing
git checkout main && git pull origin main
git merge --no-ff docs/design-spec -m "Merge design spec" && git push origin main
git checkout -b feat/engine
mkdir -p src/crucible tests
```

- [ ] **Step 2: Write pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "crucible"
version = "0.1.0"
description = "Adversarial test-hardening loop for AI-built code: Tester vs Critic closing mutation feedback, mechanical verdicts, metered spend, receipts."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Jeff Otterson" }]
dependencies = [
    "oracle-gate @ git+https://github.com/Jott2121/oracle-gate@main#subdirectory=tool",
    "agent-cost-attribution @ git+https://github.com/Jott2121/agent-cost-attribution@main",
    "mutmut>=3,<4",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
crucible = "crucible.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "slow: shells out to mutmut (minutes)",
    "integration: real model APIs (never in CI)",
]
addopts = "-m 'not integration' --ignore=tests/fixtures"
```

- [ ] **Step 3: Write the failing packaging test**

`tests/test_packaging.py`:
```python
"""Prove the dependency story before building on it: crucible imports, and the two
upstream packages it extends (oracle-gate, agent-cost-attribution) import from the venv."""


def test_crucible_imports():
    import crucible
    assert crucible.__version__ == "0.1.0"


def test_oracle_gate_importable():
    from oracle_gate import providers, survivors, runner, provenance  # noqa: F401


def test_meter_importable():
    from agent_cost_attribution import pricing  # noqa: F401
    assert "fable" in pricing.PRICES
```

`src/crucible/__init__.py`:
```python
"""crucible — adversarial test-hardening for AI-built code."""
__version__ = "0.1.0"
```

`.gitignore`:
```
.venv/
__pycache__/
*.egg-info/
mutants/
.pytest_cache/
coverage.json
```

- [ ] **Step 4: Create venv, install, run tests**

```bash
cd ~/ai-agentic-code-testing
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/test_packaging.py -v
```
Expected: 3 PASS. If the oracle-gate git install fails, STOP — that is the packaging problem Task 1 exists to surface; fix oracle-gate's `tool/pyproject.toml` minimally on `feat/usage-reporting` before proceeding.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src tests .gitignore
git commit -m "feat: scaffold crucible package; prove oracle-gate + meter install from GitHub"
```

---

### Task 2: oracle-gate `complete_with_usage` (upstream PR)

**Files:**
- Modify: `~/oracle-gate/tool/oracle_gate/providers.py`
- Test: `~/oracle-gate/tool/tests/test_providers.py` (append)

**Interfaces:**
- Produces: `Provider.complete_with_usage(system, user, model=None) -> tuple[str, Usage]` where `Usage` is a frozen dataclass `Usage(input_tokens: int, output_tokens: int)`. `Provider.complete()` unchanged in behavior (now delegates). Exported: `from oracle_gate.providers import Usage`.
- Consumed by: Task 6 (crucible providers), Task 9 (loop env).

- [ ] **Step 1: Branch oracle-gate**

```bash
cd ~/oracle-gate && git checkout main && git pull && git checkout -b feat/usage-reporting
```

- [ ] **Step 2: Write failing tests** (append to `tool/tests/test_providers.py`)

```python
from oracle_gate.providers import AnthropicProvider, OpenAIProvider, Usage


def test_anthropic_parse_usage():
    data = {"content": [{"type": "text", "text": "hi"}],
            "usage": {"input_tokens": 120, "output_tokens": 45}}
    assert AnthropicProvider()._parse_usage(data) == Usage(120, 45)


def test_openai_parse_usage():
    data = {"choices": [{"message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 80}}
    assert OpenAIProvider()._parse_usage(data) == Usage(200, 80)


def test_missing_usage_is_zero_not_crash():
    assert AnthropicProvider()._parse_usage({"content": []}) == Usage(0, 0)
    assert OpenAIProvider()._parse_usage({"choices": [{"message": {"content": ""}}]}) == Usage(0, 0)
```

- [ ] **Step 3: Run to verify failure**

Run: `cd ~/oracle-gate/tool && python -m pytest tests/test_providers.py -v -k usage`
Expected: FAIL — `ImportError: cannot import name 'Usage'`.

- [ ] **Step 4: Implement in `providers.py`**

Add near the top (after imports):
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Usage:
    """Token usage for one completion, as reported by the provider (0 when absent)."""
    input_tokens: int
    output_tokens: int
```

In `class Provider`, replace the body of `complete` and add the two methods:
```python
    def _parse_usage(self, data: dict) -> Usage:
        raise NotImplementedError

    def complete(self, system: str, user: str, model: str | None = None) -> str:
        text, _ = self.complete_with_usage(system, user, model=model)
        return text

    def complete_with_usage(
        self, system: str, user: str, model: str | None = None
    ) -> tuple[str, Usage]:
        """Send one system+user turn; return (text, token usage). Network call."""
        model = model or self.default_model
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(self._body(model, system, user)).encode(),
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.load(r)
                return self._parse(data), self._parse_usage(data)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{self.name} API error {e.code}: {e.read().decode()[:800]}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"{self.name} network error: {e}") from None
```

In `OpenAIProvider`:
```python
    def _parse_usage(self, data):
        u = data.get("usage") or {}
        return Usage(int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0))
```

In `AnthropicProvider`:
```python
    def _parse_usage(self, data):
        u = data.get("usage") or {}
        return Usage(int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0))
```

- [ ] **Step 5: Run full oracle-gate suite**

Run: `cd ~/oracle-gate/tool && python -m pytest -q`
Expected: all green (19+ tests, plus the 3 new).

- [ ] **Step 6: Commit, push, PR, merge**

```bash
cd ~/oracle-gate
git add tool/oracle_gate/providers.py tool/tests/test_providers.py
git commit -m "providers: report token usage alongside completions

complete_with_usage() returns (text, Usage(input_tokens, output_tokens)) so
callers building cost accounting on top of the review gate can meter exactly
instead of estimating. complete() is unchanged and delegates."
git push -u origin feat/usage-reporting
gh pr create --fill && gh pr merge --squash --auto
```
Then repin crucible: `cd ~/ai-agentic-code-testing && .venv/bin/pip install --force-reinstall --no-deps "oracle-gate @ git+https://github.com/Jott2121/oracle-gate@main#subdirectory=tool"` and rerun `tests/test_packaging.py`.

---

### Task 3: Meter — exact cost from usage

**Files:**
- Create: `src/crucible/meter.py`
- Test: `tests/test_meter.py`

**Interfaces:**
- Consumes: `agent_cost_attribution.pricing.PRICES` ($/MTok `(input, output)` by tier), `oracle_gate.providers.Usage`.
- Produces: `cost_usd(model: str, usage: Usage) -> float` (exact, from the input/output split — not the meter's blended estimate); `RATES_EXTRA: dict[str, tuple[float, float]]` for models the meter doesn't price (GPT). Raises `UnpricedModel` for unknown models — a run must never silently price at a wrong rate (fail closed, like oracle-gate's `UnsupportedMutmut`).

- [ ] **Step 1: Write failing tests** — `tests/test_meter.py`

```python
import pytest
from oracle_gate.providers import Usage

from crucible.meter import UnpricedModel, cost_usd


def test_claude_tier_priced_from_meter_table():
    # sonnet: $3/MTok in, $15/MTok out (agent-cost-attribution PRICES)
    assert cost_usd("claude-sonnet-5", Usage(1_000_000, 1_000_000)) == pytest.approx(18.0)


def test_fable_tier():
    assert cost_usd("claude-fable-5", Usage(2_000_000, 0)) == pytest.approx(20.0)


def test_gpt_priced_from_extra_table():
    # RATES_EXTRA carries what the meter doesn't: gpt-5.6 at ($1.75, $14) per MTok
    assert cost_usd("gpt-5.6", Usage(1_000_000, 1_000_000)) == pytest.approx(15.75)


def test_unknown_model_fails_closed():
    with pytest.raises(UnpricedModel):
        cost_usd("mystery-model-9", Usage(10, 10))
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_meter.py -v`
Expected: FAIL — `ModuleNotFoundError: crucible.meter`.

- [ ] **Step 3: Implement** — `src/crucible/meter.py`

```python
"""Exact dollar cost from provider-reported usage.

agent-cost-attribution prices with a blended-rate ESTIMATE because its telemetry has no
input/output split. Crucible has the split (oracle_gate Usage), so it prices exactly from
the same PRICES table. Models the meter doesn't know (GPT) live in RATES_EXTRA. An unknown
model raises rather than pricing wrong: a cost-per-kill paper cannot contain a guessed rate.
"""
from __future__ import annotations

from agent_cost_attribution.pricing import PRICES, _tier
from oracle_gate.providers import Usage

# $ per 1M tokens (input, output). Verify against the provider's live pricing page
# when a rate is first used in a paid run; update here with the verification date.
RATES_EXTRA = {
    "gpt-5.6": (1.75, 14.0),  # placeholder — MUST be verified before first paid GPT run
}


class UnpricedModel(ValueError):
    """No verified rate for this model; refusing to guess."""


def _rates(model: str) -> tuple[float, float]:
    tier = _tier(model)
    if tier is not None:
        return PRICES[tier]
    for prefix, rates in RATES_EXTRA.items():
        if (model or "").lower().startswith(prefix):
            return rates
    raise UnpricedModel(f"no verified $/MTok rate for {model!r}; add it to RATES_EXTRA")


def cost_usd(model: str, usage: Usage) -> float:
    inp, outp = _rates(model)
    return (usage.input_tokens * inp + usage.output_tokens * outp) / 1_000_000.0
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_meter.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/meter.py tests/test_meter.py
git commit -m "feat: exact cost from usage; unknown models fail closed"
```

---

### Task 4: Mutation engine seam + mutmut adapter

**Files:**
- Create: `src/crucible/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `oracle_gate.runner.run_mutation(cwd, run) -> (counts, results_text)`, `oracle_gate.survivors.parse_results(text) -> list[Mutant]`, `oracle_gate.survivors.undetected(mutants) -> list[Mutant]` (`Mutant` has `.id`, `.status`).
- Produces:
  - `MutationOutcome` dataclass: `counts: dict`, `survivors: list[str]` (mutant ids), `all_mutants: int`.
  - `MutmutEngine(cwd, run=subprocess.run)` with `.measure() -> MutationOutcome` and `.survivor_diff(mutant_id) -> str` (via `mutmut show <id>`).
  - `write_scope(pyproject_path: Path, source_paths: list[str]) -> None` — sets `[tool.mutmut] source_paths` in a subject CLONE's pyproject (appends the table if absent, replaces it if present). Refuses (raises `ScopeError`) if the pyproject file does not exist.

- [ ] **Step 1: Write failing tests** — `tests/test_engine.py`

```python
from pathlib import Path

import pytest

from crucible.engine import MutationOutcome, MutmutEngine, ScopeError, write_scope

RESULTS = """\
subject_pkg.calc.x_clamp__mutmut_1: killed
subject_pkg.calc.x_clamp__mutmut_2: survived
subject_pkg.calc.x_rate__mutmut_1: survived
"""


class FakeRun:
    """Scripted subprocess.run: returns canned (returncode, stdout) by command."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def __call__(self, cmd, cwd=None, capture_output=True, text=True):
        self.calls.append(cmd)
        key = " ".join(cmd[2:])  # drop "python -m"
        rc, out = self.script.get(key, (0, ""))

        class P:
            returncode, stdout, stderr = rc, out, ""

        return P()


def test_measure_returns_survivor_ids(tmp_path):
    (tmp_path / "mutants").mkdir()
    (tmp_path / "mutants" / "mutmut-cicd-stats.json").write_text(
        '{"killed": 1, "survived": 2, "no_coverage": 0, "timeout": 0}'
    )
    run = FakeRun({
        "mutmut --version": (0, "mutmut, version 3.6.0"),
        "mutmut run": (2, ""),
        "mutmut export-cicd-stats": (0, ""),
        "mutmut results --all true": (0, RESULTS),
    })
    outcome = MutmutEngine(tmp_path, run=run).measure()
    assert isinstance(outcome, MutationOutcome)
    assert outcome.survivors == [
        "subject_pkg.calc.x_clamp__mutmut_2",
        "subject_pkg.calc.x_rate__mutmut_1",
    ]
    assert outcome.all_mutants == 3


def test_survivor_diff_shells_to_mutmut_show(tmp_path):
    run = FakeRun({"mutmut show subject_pkg.calc.x_clamp__mutmut_2": (0, "--- diff ---")})
    diff = MutmutEngine(tmp_path, run=run).survivor_diff("subject_pkg.calc.x_clamp__mutmut_2")
    assert diff == "--- diff ---"


def test_write_scope_appends_table(tmp_path):
    py = tmp_path / "pyproject.toml"
    py.write_text('[project]\nname = "subject"\n')
    write_scope(py, ["subject_pkg/calc.py"])
    text = py.read_text()
    assert "[tool.mutmut]" in text and 'source_paths = ["subject_pkg/calc.py"]' in text


def test_write_scope_replaces_existing_table(tmp_path):
    py = tmp_path / "pyproject.toml"
    py.write_text('[project]\nname = "s"\n\n[tool.mutmut]\nsource_paths = ["old.py"]\n')
    write_scope(py, ["new.py"])
    text = py.read_text()
    assert 'source_paths = ["new.py"]' in text and "old.py" not in text


def test_write_scope_requires_pyproject(tmp_path):
    with pytest.raises(ScopeError):
        write_scope(tmp_path / "pyproject.toml", ["x.py"])
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: crucible.engine`.

- [ ] **Step 3: Implement** — `src/crucible/engine.py`

```python
"""Mutation engine seam. mutmut today; the interface is the contract, so another engine
(Cosmic Ray) can slot in later without touching the loop. All heavy lifting delegates to
oracle-gate's verified runner/parsers — crucible never parses mutmut output itself.

Scope note: mutmut reads its scope ONLY from [tool.mutmut] source_paths in the working
directory's pyproject. oracle-gate (a verifier) refuses to touch that config; crucible (a
generator operating on a disposable CLONE) sets it deliberately via write_scope().
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from oracle_gate.runner import run_mutation
from oracle_gate.survivors import parse_results, undetected


class ScopeError(RuntimeError):
    """The subject clone has no pyproject.toml to carry [tool.mutmut] scope."""


@dataclass(frozen=True)
class MutationOutcome:
    counts: dict
    survivors: list[str]
    all_mutants: int


class MutmutEngine:
    def __init__(self, cwd, run=subprocess.run):
        self.cwd = Path(cwd)
        self.run = run

    def measure(self) -> MutationOutcome:
        counts, results_text = run_mutation(self.cwd, run=self.run)
        mutants = parse_results(results_text)
        return MutationOutcome(
            counts=counts,
            survivors=[m.id for m in undetected(mutants)],
            all_mutants=len(mutants),
        )

    def survivor_diff(self, mutant_id: str) -> str:
        proc = self.run(
            [sys.executable, "-m", "mutmut", "show", mutant_id],
            cwd=str(self.cwd), capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"`mutmut show {mutant_id}` failed: {proc.stderr}")
        return proc.stdout


_MUTMUT_TABLE = re.compile(r"\[tool\.mutmut\][^\[]*", re.S)


def write_scope(pyproject_path: Path, source_paths: list[str]) -> None:
    pyproject_path = Path(pyproject_path)
    if not pyproject_path.exists():
        raise ScopeError(f"{pyproject_path} does not exist; cannot scope mutmut")
    paths = ", ".join(f'"{p}"' for p in source_paths)
    table = f'[tool.mutmut]\nsource_paths = [{paths}]\n'
    text = pyproject_path.read_text()
    if _MUTMUT_TABLE.search(text):
        text = _MUTMUT_TABLE.sub(table, text)
    else:
        text = text.rstrip() + "\n\n" + table
    pyproject_path.write_text(text)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_engine.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/engine.py tests/test_engine.py
git commit -m "feat: mutation engine seam; mutmut adapter delegates to oracle-gate runner"
```

---

### Task 5: Pytest runner (the IO edge for test execution)

**Files:**
- Create: `src/crucible/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Produces: `TestRunResult` dataclass (`passed: bool`, `returncode: int`, `output: str`); `run_tests(cwd, test_paths: list[str] | None = None, timeout: int = 300, run=subprocess.run) -> TestRunResult`. `test_paths=None` runs the whole suite. Timeout expiry returns `TestRunResult(passed=False, returncode=-1, output="TIMEOUT ...")` — a hung generated test is a failed test, not a crashed loop.

- [ ] **Step 1: Write failing tests** — `tests/test_runner.py`

```python
import subprocess

from crucible.runner import TestRunResult, run_tests


def _fake(rc, out):
    def run(cmd, cwd=None, capture_output=True, text=True, timeout=None):
        class P:
            returncode, stdout, stderr = rc, out, ""
        return P()
    return run


def test_green_suite():
    r = run_tests("/subject", run=_fake(0, "3 passed"))
    assert r == TestRunResult(passed=True, returncode=0, output="3 passed")


def test_red_suite():
    r = run_tests("/subject", test_paths=["tests/crucible_a_test.py"], run=_fake(1, "1 failed"))
    assert r.passed is False and r.returncode == 1


def test_timeout_is_a_failure_not_a_crash():
    def run(cmd, cwd=None, capture_output=True, text=True, timeout=None):
        raise subprocess.TimeoutExpired(cmd, timeout)
    r = run_tests("/subject", timeout=5, run=run)
    assert r.passed is False and r.returncode == -1 and "TIMEOUT" in r.output
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: crucible.runner`.

- [ ] **Step 3: Implement** — `src/crucible/runner.py`

```python
"""Run the subject's tests in a subprocess. The only place pytest is invoked."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class TestRunResult:
    passed: bool
    returncode: int
    output: str


def run_tests(cwd, test_paths=None, timeout=300, run=subprocess.run) -> TestRunResult:
    cmd = [sys.executable, "-m", "pytest", "-q", *(test_paths or [])]
    try:
        proc = run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return TestRunResult(passed=False, returncode=-1, output=f"TIMEOUT after {timeout}s")
    return TestRunResult(
        passed=proc.returncode == 0,
        returncode=proc.returncode,
        output=(proc.stdout or "") + (proc.stderr or ""),
    )
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_runner.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/runner.py tests/test_runner.py
git commit -m "feat: pytest runner edge; timeouts are failures, not crashes"
```

---

### Task 6: Providers extension (big-output Anthropic, fake provider, registry)

**Files:**
- Create: `src/crucible/providers_ext.py`
- Test: `tests/test_providers_ext.py`

**Interfaces:**
- Consumes: `oracle_gate.providers.{AnthropicProvider, OpenAIProvider, Provider, Usage}`.
- Produces: `get_provider(name) -> Provider` for names `"anthropic"`, `"openai"`, `"fake"`. `LongAnthropicProvider` overrides `_body` with `max_tokens=16000` (test files are long; oracle-gate's 4096 default truncates). `FakeProvider(replies: list[str])` returns scripted replies with `Usage(1000, 500)` each and never touches the network — the CLI's fake mode and all loop tests use it.

- [ ] **Step 1: Write failing tests** — `tests/test_providers_ext.py`

```python
import pytest
from oracle_gate.providers import Usage

from crucible.providers_ext import FakeProvider, LongAnthropicProvider, get_provider


def test_long_anthropic_raises_max_tokens():
    body = LongAnthropicProvider()._body("m", "sys", "user")
    assert body["max_tokens"] == 16000


def test_fake_provider_scripts_replies():
    p = FakeProvider(["first", "second"])
    text, usage = p.complete_with_usage("s", "u")
    assert text == "first" and usage == Usage(1000, 500)
    text, _ = p.complete_with_usage("s", "u")
    assert text == "second"


def test_fake_provider_exhausted_raises():
    p = FakeProvider([])
    with pytest.raises(RuntimeError, match="exhausted"):
        p.complete_with_usage("s", "u")


def test_registry():
    assert get_provider("anthropic").__class__ is LongAnthropicProvider
    assert get_provider("openai").name == "openai"
    with pytest.raises(KeyError):
        get_provider("nope")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_providers_ext.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `src/crucible/providers_ext.py`

```python
"""Crucible's provider registry: oracle-gate's providers, extended not forked.

LongAnthropicProvider only raises max_tokens (generated test files exceed oracle-gate's
review-sized 4096 default). FakeProvider makes every loop path testable offline.
"""
from __future__ import annotations

from oracle_gate.providers import AnthropicProvider, OpenAIProvider, Provider, Usage


class LongAnthropicProvider(AnthropicProvider):
    def _body(self, model, system, user):
        body = super()._body(model, system, user)
        body["max_tokens"] = 16000
        return body


class FakeProvider(Provider):
    name = "fake"
    lineage = "fake"
    default_model = "fake-model"

    def __init__(self, replies):
        self.replies = list(replies)

    def complete_with_usage(self, system, user, model=None):
        if not self.replies:
            raise RuntimeError("FakeProvider exhausted: more model calls than scripted replies")
        return self.replies.pop(0), Usage(1000, 500)


def get_provider(name: str) -> Provider:
    registry = {
        "anthropic": LongAnthropicProvider,
        "openai": OpenAIProvider,
        "fake": lambda: FakeProvider([]),
    }
    if name not in registry:
        raise KeyError(f"unknown provider {name!r}; known: {sorted(registry)}")
    return registry[name]()
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_providers_ext.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/providers_ext.py tests/test_providers_ext.py
git commit -m "feat: provider registry — long-output anthropic, offline fake"
```

---

### Task 7: Roles and prompts (versioned, hashed)

**Files:**
- Create: `src/crucible/prompts/tester.md`, `src/crucible/prompts/critic.md`
- Create: `src/crucible/roles.py`
- Test: `tests/test_roles.py`

**Interfaces:**
- Produces: `build_tester_prompt(module_path: str, module_source: str) -> RolePrompt`, `build_critic_prompt(module_path: str, module_source: str, survivor_diffs: dict[str, str]) -> RolePrompt`. `RolePrompt` dataclass: `system: str`, `user: str`, `prompt_sha256: str` (hash of template file + assembled user text — receipts pin exactly what each role saw). Templates use `{placeholders}` filled by `str.format`.

- [ ] **Step 1: Write prompt templates**

`src/crucible/prompts/tester.md`:
```markdown
You write pytest tests for Python modules. Rules, all mandatory:
- Output EXACTLY ONE fenced python code block containing one complete test file, nothing else.
- Tests must import the module under test from its installed location, not by path hacks.
- Every test must assert on OUTPUT VALUES computed independently by you from reading the spec
  of the function (docstrings/signatures). Never call the function to produce its own expected value.
- Do not modify, skip, or weaken anything; you may only add tests.
- Prefer boundary cases (empty, zero, negative, ordering, off-by-one) over happy paths.
```

`src/crucible/prompts/critic.md`:
```markdown
You are a test critic. Below is a Python module and a set of SURVIVING MUTANTS: small
deliberate defects that the current test suite FAILED to detect. Your only job is to write
tests that would FAIL on the mutated code but PASS on the original shown here.

Rules, all mandatory:
- Output EXACTLY ONE fenced python code block containing one complete test file, nothing else.
- For each mutant diff, derive what behavior difference it causes, and write a test asserting
  the ORIGINAL behavior with an independently computed expected value.
- Never assert "whatever the code currently returns"; compute expected values yourself.
- You may only add tests. Do not touch existing tests or source.
```

- [ ] **Step 2: Write failing tests** — `tests/test_roles.py`

```python
from crucible.roles import RolePrompt, build_critic_prompt, build_tester_prompt


def test_tester_prompt_carries_module():
    p = build_tester_prompt("pkg/calc.py", "def f(): ...")
    assert isinstance(p, RolePrompt)
    assert "pkg/calc.py" in p.user and "def f(): ..." in p.user
    assert len(p.prompt_sha256) == 64


def test_critic_prompt_carries_survivor_diffs():
    p = build_critic_prompt("pkg/calc.py", "def f(): ...", {"m1": "--- d1 ---", "m2": "--- d2 ---"})
    assert "m1" in p.user and "--- d1 ---" in p.user and "--- d2 ---" in p.user


def test_hash_changes_when_inputs_change():
    a = build_tester_prompt("p.py", "x = 1")
    b = build_tester_prompt("p.py", "x = 2")
    assert a.prompt_sha256 != b.prompt_sha256


def test_hash_stable_for_same_inputs():
    assert (
        build_tester_prompt("p.py", "x = 1").prompt_sha256
        == build_tester_prompt("p.py", "x = 1").prompt_sha256
    )
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_roles.py -v`
Expected: FAIL — `ModuleNotFoundError: crucible.roles`.

- [ ] **Step 4: Implement** — `src/crucible/roles.py`

```python
"""Assemble Tester/Critic prompts from versioned template files and hash what was sent.

The hash goes into every receipt: a reader of the paper can verify exactly which prompt
produced which tests, and any prompt edit changes the hash trail.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class RolePrompt:
    system: str
    user: str
    prompt_sha256: str


def _template(name: str) -> str:
    return (resources.files("crucible") / "prompts" / name).read_text()


def _finish(system: str, user: str) -> RolePrompt:
    digest = hashlib.sha256((system + "\x00" + user).encode()).hexdigest()
    return RolePrompt(system=system, user=user, prompt_sha256=digest)


def build_tester_prompt(module_path: str, module_source: str) -> RolePrompt:
    system = _template("tester.md")
    user = f"Module `{module_path}`:\n\n```python\n{module_source}\n```\n\nWrite the test file now."
    return _finish(system, user)


def build_critic_prompt(module_path, module_source, survivor_diffs) -> RolePrompt:
    system = _template("critic.md")
    diffs = "\n\n".join(f"### Mutant `{mid}`\n```diff\n{d}\n```" for mid, d in survivor_diffs.items())
    user = (
        f"Module `{module_path}`:\n\n```python\n{module_source}\n```\n\n"
        f"## Surviving mutants ({len(survivor_diffs)})\n\n{diffs}\n\nWrite the test file now."
    )
    return _finish(system, user)
```

Also add to `pyproject.toml` under `[tool.setuptools.packages.find]` section (package data):
```toml
[tool.setuptools.package-data]
crucible = ["prompts/*.md"]
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pip install -e ".[dev]" -q && .venv/bin/python -m pytest tests/test_roles.py -v`
Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/crucible/roles.py src/crucible/prompts tests/test_roles.py pyproject.toml
git commit -m "feat: versioned role prompts, sha256-pinned into receipts"
```

---

### Task 8: Guardrails (anti-gaming layer)

**Files:**
- Create: `src/crucible/guardrails.py`
- Test: `tests/test_guardrails.py`

**Interfaces:**
- Consumes: `crucible.runner.run_tests`.
- Produces:
  - `extract_test_file(model_output: str) -> str` — the contents of exactly one fenced python block; raises `GuardrailViolation` for zero or multiple blocks, or a block with no `assert`.
  - `test_filename(round_no: int, arm: str) -> str` — e.g. `crucible_r2_loop_test.py` (always the `crucible_` prefix).
  - `validate_new_tests(cwd, test_path, run_tests_fn) -> None` — the new file must PASS on pristine code, twice (flake check). Raises `GuardrailViolation("invalid: ...")` or `GuardrailViolation("flaky: ...")`.
  - `assert_add_only(git_status_output: str, allowed_new: list[str]) -> None` — every changed path in `git status --porcelain` output must be an untracked (`??`) entry in `allowed_new`; anything else raises `GuardrailViolation`.

- [ ] **Step 1: Write failing tests** — `tests/test_guardrails.py`

```python
import pytest

from crucible.guardrails import (
    GuardrailViolation,
    assert_add_only,
    extract_test_file,
    test_filename,
    validate_new_tests,
)
from crucible.runner import TestRunResult


def test_extracts_single_python_block():
    out = "Here you go:\n```python\ndef test_a():\n    assert 1 == 1\n```\nDone."
    assert extract_test_file(out) == "def test_a():\n    assert 1 == 1"


def test_zero_blocks_rejected():
    with pytest.raises(GuardrailViolation, match="one fenced python block"):
        extract_test_file("no code here")


def test_two_blocks_rejected():
    two = "```python\nassert True\n```\n```python\nassert True\n```"
    with pytest.raises(GuardrailViolation, match="one fenced python block"):
        extract_test_file(two)


def test_no_assert_rejected():
    with pytest.raises(GuardrailViolation, match="no assert"):
        extract_test_file("```python\ndef test_a():\n    pass\n```")


def test_filename_prefix():
    assert test_filename(2, "loop") == "crucible_r2_loop_test.py"


def test_validate_passes_when_green_twice(tmp_path):
    calls = []

    def fake_run(cwd, test_paths=None, timeout=300):
        calls.append(test_paths)
        return TestRunResult(True, 0, "ok")

    validate_new_tests(tmp_path, "tests/crucible_r1_loop_test.py", fake_run)
    assert len(calls) == 2  # flake check = run twice


def test_validate_rejects_red_on_pristine(tmp_path):
    def fake_run(cwd, test_paths=None, timeout=300):
        return TestRunResult(False, 1, "1 failed")

    with pytest.raises(GuardrailViolation, match="invalid"):
        validate_new_tests(tmp_path, "tests/crucible_r1_loop_test.py", fake_run)


def test_validate_rejects_flaky(tmp_path):
    results = [TestRunResult(True, 0, "ok"), TestRunResult(False, 1, "flaked")]

    def fake_run(cwd, test_paths=None, timeout=300):
        return results.pop(0)

    with pytest.raises(GuardrailViolation, match="flaky"):
        validate_new_tests(tmp_path, "tests/crucible_r1_loop_test.py", fake_run)


def test_add_only_accepts_expected_untracked():
    assert_add_only("?? tests/crucible_r1_loop_test.py\n", ["tests/crucible_r1_loop_test.py"])


def test_add_only_rejects_source_modification():
    status = " M subject_pkg/calc.py\n?? tests/crucible_r1_loop_test.py\n"
    with pytest.raises(GuardrailViolation, match="add-only"):
        assert_add_only(status, ["tests/crucible_r1_loop_test.py"])


def test_add_only_rejects_unexpected_new_file():
    with pytest.raises(GuardrailViolation, match="add-only"):
        assert_add_only("?? sneaky.py\n", ["tests/crucible_r1_loop_test.py"])
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_guardrails.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `src/crucible/guardrails.py`

```python
"""The anti-gaming layer. Agents make tests "pass" by weakening things (Kent Beck's
observation; our standard's failure-mode list). Crucible never trusts the model's output
shape or conduct — every rule here is a hard check, not a prompt instruction.
"""
from __future__ import annotations

import re
from pathlib import Path


class GuardrailViolation(RuntimeError):
    """Model output broke a hard rule; the round rejects it (never a crash)."""


_PY_BLOCK = re.compile(r"```python\n(.*?)```", re.S)


def extract_test_file(model_output: str) -> str:
    blocks = _PY_BLOCK.findall(model_output or "")
    if len(blocks) != 1:
        raise GuardrailViolation(
            f"expected exactly one fenced python block, found {len(blocks)}"
        )
    content = blocks[0].strip("\n")
    if "assert" not in content:
        raise GuardrailViolation("no assert in generated test file")
    return content


def test_filename(round_no: int, arm: str) -> str:
    return f"crucible_r{round_no}_{arm}_test.py"


def validate_new_tests(cwd, test_path, run_tests_fn) -> None:
    """New tests must pass on PRISTINE code (else they encode a wrong oracle), twice
    (else they're flaky and their kills are noise)."""
    first = run_tests_fn(cwd, test_paths=[str(test_path)])
    if not first.passed:
        raise GuardrailViolation(f"invalid: fails on pristine code\n{first.output[-2000:]}")
    second = run_tests_fn(cwd, test_paths=[str(test_path)])
    if not second.passed:
        raise GuardrailViolation(f"flaky: passed once then failed\n{second.output[-2000:]}")


def assert_add_only(git_status_output: str, allowed_new) -> None:
    allowed = {str(Path(p)) for p in allowed_new}
    for line in (git_status_output or "").splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip()
        if code == "??" and str(Path(path)) in allowed:
            continue
        raise GuardrailViolation(f"add-only violated: unexpected change {line.strip()!r}")
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_guardrails.py -v`
Expected: 11 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/guardrails.py tests/test_guardrails.py
git commit -m "feat: guardrails — single-block extraction, pristine validity, flake check, add-only"
```

---

### Task 9: The loop (pure core)

**Files:**
- Create: `src/crucible/loop.py`
- Test: `tests/test_loop.py`

**Interfaces:**
- Consumes: `MutationOutcome` (Task 4), `GuardrailViolation` (Task 8), `Usage` (oracle-gate).
- Produces:
  - `LoopConfig` dataclass: `max_rounds: int = 5`, `dry_rounds: int = 2`, `arm: str = "loop"`.
  - `RoundRecord` dataclass: `round: int`, `role: str` ("tester"|"critic"), `prompt_sha256: str`, `model: str`, `usage_in: int`, `usage_out: int`, `cost_usd: float`, `test_file: str | None`, `survivors_before: list[str]`, `survivors_after: list[str]`, `kills: list[str]`, `status: str` ("ok"|"rejected"|"aborted"), `note: str`.
  - `LoopResult` dataclass: `rounds: list[RoundRecord]`, `verdict: str` ("dry"|"cap"|"clean"|"aborted"), `total_cost_usd: float`.
  - `harden(env, cfg: LoopConfig) -> LoopResult` — the loop. `oneshot(env, cfg) -> LoopResult` — round 0 only.
  - The `env` duck-type (documented in the module docstring, implemented for real in Task 11's CLI and faked in tests):
    - `env.measure() -> MutationOutcome`
    - `env.survivor_diff(mutant_id) -> str`
    - `env.call_tester() -> RoundReply` / `env.call_critic(survivor_diffs: dict[str,str]) -> RoundReply` where `RoundReply` = `(text: str, prompt_sha256: str, model: str, usage: Usage)` (a small frozen dataclass in loop.py)
    - `env.write_test_file(round_no, arm, content) -> str` (returns repo-relative path; performs the add-only check)
    - `env.validate(test_path) -> None` (raises `GuardrailViolation`)
    - `env.remove_test_file(path) -> None` (a rejected round leaves no trace)
    - `env.cost_usd(model, usage) -> float`
- Loop semantics (the contract the tests pin):
  1. Round 0: tester writes tests → guardrail-validate → measure ⇒ baseline survivors. `oneshot` stops here.
  2. Rounds 1..max: critic gets ALL current survivor diffs → new test file → validate → measure ⇒ kills = before − after.
  3. A `GuardrailViolation` marks the round `rejected` (file removed, no kills) — it counts toward dryness.
  4. Dry = `dry_rounds` consecutive rounds with zero kills ⇒ verdict "dry". Zero survivors ⇒ "clean". Round cap ⇒ "cap".
  5. A model-call exception aborts the loop with verdict "aborted" (retries live at the env layer, Task 11).

- [ ] **Step 1: Write failing tests** — `tests/test_loop.py`

```python
import pytest
from oracle_gate.providers import Usage

from crucible.engine import MutationOutcome
from crucible.guardrails import GuardrailViolation
from crucible.loop import LoopConfig, LoopResult, RoundReply, harden, oneshot


def outcome(survivors):
    return MutationOutcome(counts={}, survivors=list(survivors), all_mutants=10)


class FakeEnv:
    """Scripted env: measurements pop off a list; roles return canned replies."""

    def __init__(self, measurements, reject_rounds=(), fail_calls=False):
        self.measurements = list(measurements)
        self.reject_rounds = set(reject_rounds)
        self.fail_calls = fail_calls
        self.written, self.removed = [], []
        self._round = 0

    def measure(self):
        return self.measurements.pop(0)

    def survivor_diff(self, mid):
        return f"diff-of-{mid}"

    def _reply(self):
        if self.fail_calls:
            raise RuntimeError("model down")
        return RoundReply("```python\nassert True\n```", "a" * 64, "claude-sonnet-5", Usage(10, 5))

    def call_tester(self):
        return self._reply()

    def call_critic(self, survivor_diffs):
        self.last_diffs = survivor_diffs
        return self._reply()

    def write_test_file(self, round_no, arm, content):
        self._round = round_no
        path = f"tests/crucible_r{round_no}_{arm}_test.py"
        self.written.append(path)
        return path

    def validate(self, test_path):
        if self._round in self.reject_rounds:
            raise GuardrailViolation("invalid: scripted rejection")

    def remove_test_file(self, path):
        self.removed.append(path)

    def cost_usd(self, model, usage):
        return 0.01


def test_oneshot_is_round_zero_only():
    env = FakeEnv([outcome(["m1", "m2"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert len(result.rounds) == 1
    assert result.rounds[0].role == "tester"
    assert result.rounds[0].survivors_after == ["m1", "m2"]


def test_loop_records_kills_and_stops_clean():
    env = FakeEnv([outcome(["m1", "m2"]), outcome(["m2"]), outcome([])])
    result = harden(env, LoopConfig())
    assert result.verdict == "clean"
    assert result.rounds[1].kills == ["m1"]
    assert result.rounds[2].kills == ["m2"]


def test_loop_goes_dry_after_k_zero_kill_rounds():
    env = FakeEnv([outcome(["m1"]), outcome(["m1"]), outcome(["m1"])])
    result = harden(env, LoopConfig(dry_rounds=2))
    assert result.verdict == "dry"
    assert len(result.rounds) == 3  # tester + 2 dry critic rounds


def test_loop_hits_round_cap():
    ms = [outcome(["m1", "m2"])] + [outcome(["m1"])] * 9
    env = FakeEnv(ms)
    result = harden(env, LoopConfig(max_rounds=3, dry_rounds=99))
    assert result.verdict == "cap"
    assert len(result.rounds) == 4  # tester + 3 critic rounds


def test_rejected_round_removes_file_and_counts_dry():
    env = FakeEnv([outcome(["m1"]), outcome(["m1"])], reject_rounds={1})
    result = harden(env, LoopConfig(dry_rounds=2))
    assert result.rounds[1].status == "rejected"
    assert env.removed == ["tests/crucible_r1_loop_test.py"]
    # rejected round killed nothing; one more zero-kill round => dry
    assert result.verdict == "dry"


def test_model_failure_aborts():
    env = FakeEnv([outcome(["m1"])])
    env.fail_calls = False
    result_env = FakeEnv([outcome(["m1"])])
    result_env.fail_calls = True
    result = harden(result_env, LoopConfig())
    assert result.verdict == "aborted"
    assert result.rounds[-1].status == "aborted"


def test_total_cost_accumulates():
    env = FakeEnv([outcome(["m1"]), outcome([])])
    result = harden(env, LoopConfig())
    assert result.total_cost_usd == pytest.approx(0.02)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_loop.py -v`
Expected: FAIL — `ModuleNotFoundError: crucible.loop`.

- [ ] **Step 3: Implement** — `src/crucible/loop.py`

```python
"""The adversarial loop. Pure control flow: every effect goes through the injected env,
so this file is unit-tested with fakes and mutation-tested for real (dogfood, Task 12).

Round 0: the Tester writes tests from the module alone. Rounds 1..N: the Critic sees the
named survivors and aims at exactly those. Verdicts are mechanical throughout — a mutant
is killed by pytest or it survives; no model opinion is ever consulted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from oracle_gate.providers import Usage

from crucible.guardrails import GuardrailViolation


@dataclass(frozen=True)
class RoundReply:
    text: str
    prompt_sha256: str
    model: str
    usage: Usage


@dataclass(frozen=True)
class LoopConfig:
    max_rounds: int = 5
    dry_rounds: int = 2
    arm: str = "loop"


@dataclass
class RoundRecord:
    round: int
    role: str
    prompt_sha256: str = ""
    model: str = ""
    usage_in: int = 0
    usage_out: int = 0
    cost_usd: float = 0.0
    test_file: str | None = None
    survivors_before: list[str] = field(default_factory=list)
    survivors_after: list[str] = field(default_factory=list)
    kills: list[str] = field(default_factory=list)
    status: str = "ok"
    note: str = ""


@dataclass
class LoopResult:
    rounds: list[RoundRecord]
    verdict: str
    total_cost_usd: float


def _round(env, cfg, round_no, role, survivors_before) -> RoundRecord:
    rec = RoundRecord(round=round_no, role=role, survivors_before=list(survivors_before))
    try:
        if role == "tester":
            reply = env.call_tester()
        else:
            diffs = {mid: env.survivor_diff(mid) for mid in survivors_before}
            reply = env.call_critic(diffs)
    except Exception as exc:  # model/network failure after env-level retries
        rec.status, rec.note = "aborted", f"model call failed: {exc}"
        return rec

    rec.prompt_sha256, rec.model = reply.prompt_sha256, reply.model
    rec.usage_in, rec.usage_out = reply.usage.input_tokens, reply.usage.output_tokens
    rec.cost_usd = env.cost_usd(reply.model, reply.usage)

    path = env.write_test_file(round_no, cfg.arm, reply.text)
    rec.test_file = path
    try:
        env.validate(path)
    except GuardrailViolation as exc:
        env.remove_test_file(path)
        rec.status, rec.note, rec.test_file = "rejected", str(exc), None
        rec.survivors_after = list(survivors_before)
        return rec

    after = env.measure()
    rec.survivors_after = list(after.survivors)
    rec.kills = [m for m in survivors_before if m not in set(after.survivors)]
    return rec


def _run(env, cfg, rounds_budget) -> LoopResult:
    rounds: list[RoundRecord] = []

    first = _round(env, cfg, 0, "tester", survivors_before=[])
    rounds.append(first)
    if first.status == "aborted":
        return LoopResult(rounds, "aborted", _cost(rounds))
    survivors = first.survivors_after

    dry = 0
    for n in range(1, rounds_budget + 1):
        if not survivors:
            return LoopResult(rounds, "clean", _cost(rounds))
        rec = _round(env, cfg, n, "critic", survivors)
        rounds.append(rec)
        if rec.status == "aborted":
            return LoopResult(rounds, "aborted", _cost(rounds))
        survivors = rec.survivors_after
        dry = dry + 1 if not rec.kills else 0
        if dry >= cfg.dry_rounds:
            return LoopResult(rounds, "dry", _cost(rounds))

    verdict = "clean" if not survivors else "cap"
    return LoopResult(rounds, verdict, _cost(rounds))


def _cost(rounds) -> float:
    return sum(r.cost_usd for r in rounds)


def harden(env, cfg: LoopConfig) -> LoopResult:
    return _run(env, cfg, rounds_budget=cfg.max_rounds)


def oneshot(env, cfg: LoopConfig) -> LoopResult:
    return _run(env, cfg, rounds_budget=0)
```

NOTE for the implementer: `test_oneshot_is_round_zero_only` expects verdict semantics from `_run` with `rounds_budget=0` — round 0 runs, measures, and returns "clean" or "cap" depending on survivors; the test only checks rounds/role/survivors, not the verdict. `test_model_failure_aborts` expects the tester-round abort path.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_loop.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/crucible/loop.py tests/test_loop.py
git commit -m "feat: adversarial loop core — pure control flow, mechanical verdicts"
```

---

### Task 10: Receipts (append-per-round JSONL, SHA-bound)

**Files:**
- Create: `src/crucible/receipts.py`
- Test: `tests/test_receipts.py`

**Interfaces:**
- Consumes: `RoundRecord`, `LoopResult` (Task 9).
- Produces: `ReceiptWriter(run_dir: Path, meta: dict)` — writes `meta.json` on creation (subject repo, head SHA, arm, models, config, started_at) and `receipt.jsonl` one line per round via `.append(record: RoundRecord)`; `.finish(verdict, total_cost_usd)` writes `result.json`. `load_run(run_dir) -> dict` reads all three back. Crash-safety contract: every `append` opens/writes/closes (a crash loses at most the in-flight round).

- [ ] **Step 1: Write failing tests** — `tests/test_receipts.py`

```python
import json

from crucible.loop import RoundRecord
from crucible.receipts import ReceiptWriter, load_run


def test_receipt_roundtrip(tmp_path):
    w = ReceiptWriter(tmp_path / "run1", {"subject": "graph-guard", "head_sha": "abc123", "arm": "loop"})
    w.append(RoundRecord(round=0, role="tester", kills=[], survivors_after=["m1"]))
    w.append(RoundRecord(round=1, role="critic", kills=["m1"], survivors_after=[]))
    w.finish("clean", 0.42)

    run = load_run(tmp_path / "run1")
    assert run["meta"]["head_sha"] == "abc123"
    assert [r["round"] for r in run["rounds"]] == [0, 1]
    assert run["rounds"][1]["kills"] == ["m1"]
    assert run["result"] == {"verdict": "clean", "total_cost_usd": 0.42}


def test_append_is_durable_per_round(tmp_path):
    w = ReceiptWriter(tmp_path / "run2", {"subject": "s", "head_sha": "x", "arm": "oneshot"})
    w.append(RoundRecord(round=0, role="tester"))
    # no finish() — simulate a crash; the round must still be on disk
    lines = (tmp_path / "run2" / "receipt.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["role"] == "tester"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_receipts.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `src/crucible/receipts.py`

```python
"""Receipts: one JSONL line per round, appended durably as the loop runs.

meta.json binds the run to the subject's commit SHA and the exact config; receipt.jsonl
carries the per-round evidence (prompt hashes, usage, kills); result.json is the verdict.
A crash loses at most the in-flight round (error-swallowing lesson: never buffer a run's
evidence in memory).
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path


class ReceiptWriter:
    def __init__(self, run_dir, meta: dict):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    def append(self, record) -> None:
        line = json.dumps(dataclasses.asdict(record))
        with open(self.run_dir / "receipt.jsonl", "a") as f:
            f.write(line + "\n")

    def finish(self, verdict: str, total_cost_usd: float) -> None:
        (self.run_dir / "result.json").write_text(
            json.dumps({"verdict": verdict, "total_cost_usd": total_cost_usd})
        )


def load_run(run_dir) -> dict:
    run_dir = Path(run_dir)
    rounds = []
    receipt = run_dir / "receipt.jsonl"
    if receipt.exists():
        rounds = [json.loads(l) for l in receipt.read_text().strip().splitlines() if l]
    result = None
    if (run_dir / "result.json").exists():
        result = json.loads((run_dir / "result.json").read_text())
    return {
        "meta": json.loads((run_dir / "meta.json").read_text()),
        "rounds": rounds,
        "result": result,
    }
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_receipts.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/receipts.py tests/test_receipts.py
git commit -m "feat: per-round durable receipts bound to subject SHA"
```

---

### Task 11: Real env + CLI (`crucible oneshot|harden`) + fixture end-to-end

**Files:**
- Create: `src/crucible/env.py`
- Create: `src/crucible/cli.py`
- Create: `tests/fixtures/subject/pyproject.toml`, `tests/fixtures/subject/subject_pkg/__init__.py`, `tests/fixtures/subject/subject_pkg/calc.py`, `tests/fixtures/subject/tests/test_calc.py`
- Test: `tests/test_env.py`, `tests/test_cli_e2e.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `SubjectEnv(subject_dir, tester_provider, tester_model, critic_provider, critic_model, module_path, run=subprocess.run)` implementing the loop's env duck-type. Model calls retry 3x with 2s/8s backoff before raising. `write_test_file` writes under `<subject>/tests/` then runs `git status --porcelain` and `assert_add_only`. `measure()` delegates to `MutmutEngine`. `head_sha()` via `oracle_gate.runner.head_sha`.
  - CLI: `crucible oneshot|harden SUBJECT_DIR --module subject_pkg/calc.py [--tester-model M] [--critic anthropic|openai|fake] [--critic-model M] [--rounds N] [--dry-rounds K] [--runs-dir DIR] [--fake-replies FILE]`. `--critic fake` + `--fake-replies replies.json` (a JSON list of model outputs) makes the whole run offline. Exit code 0 on verdicts clean/dry/cap, 3 on aborted. Prints a plain-ASCII round table and the receipt path.
  - Fixture subject: a 2-function module with deliberately weak existing tests, git-initialized by the e2e test.

- [ ] **Step 1: Create the fixture subject**

`tests/fixtures/subject/pyproject.toml`:
```toml
[project]
name = "subject-fixture"
version = "0.0.1"
requires-python = ">=3.11"

[tool.mutmut]
source_paths = ["subject_pkg/calc.py"]
pytest_add_cli_args_test_selection = ["tests/"]
```

`tests/fixtures/subject/subject_pkg/__init__.py`: empty file.

`tests/fixtures/subject/subject_pkg/calc.py`:
```python
"""Tiny HR-ish math module: the mutation target for crucible's own e2e test."""


def clamp(value, lo, hi):
    """Return value bounded to [lo, hi]."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def acceptance_rate(offers, accepts):
    """accepts/offers as a fraction; 0.0 when no offers (never divide by zero)."""
    if offers <= 0:
        return 0.0
    return accepts / offers
```

`tests/fixtures/subject/tests/test_calc.py` (deliberately weak — runs code, checks almost nothing):
```python
from subject_pkg.calc import acceptance_rate, clamp


def test_clamp_runs():
    assert clamp(5, 0, 10) == 5


def test_rate_runs():
    acceptance_rate(10, 5)  # no assertion on the value: the classic false-pass
```

- [ ] **Step 2: Write failing env tests** — `tests/test_env.py`

```python
from oracle_gate.providers import Usage

from crucible.env import SubjectEnv
from crucible.providers_ext import FakeProvider

GOOD_TESTS = """```python
from subject_pkg.calc import acceptance_rate, clamp

def test_clamp_low():
    assert clamp(-5, 0, 10) == 0

def test_rate_value():
    assert acceptance_rate(10, 5) == 0.5
```"""


def _env(tmp_path, replies):
    import shutil, subprocess
    from pathlib import Path

    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    subprocess.run(["git", "init", "-q"], cwd=subject, check=True)
    subprocess.run(["git", "add", "-A"], cwd=subject, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=subject, check=True,
    )
    p = FakeProvider(replies)
    return SubjectEnv(
        subject_dir=subject, tester_provider=p, tester_model="fake-model",
        critic_provider=p, critic_model="fake-model", module_path="subject_pkg/calc.py",
    )


def test_call_tester_returns_reply_with_hash(tmp_path):
    env = _env(tmp_path, [GOOD_TESTS])
    reply = env.call_tester()
    assert "clamp_low" in reply.text and len(reply.prompt_sha256) == 64


def test_write_and_remove_test_file_respects_add_only(tmp_path):
    env = _env(tmp_path, [])
    path = env.write_test_file(1, "loop", "def test_x():\n    assert True\n")
    assert (env.subject_dir / path).exists()
    env.remove_test_file(path)
    assert not (env.subject_dir / path).exists()


def test_retry_then_raise(tmp_path):
    class DyingProvider(FakeProvider):
        def __init__(self):
            super().__init__([])
            self.calls = 0

        def complete_with_usage(self, system, user, model=None):
            self.calls += 1
            raise RuntimeError("boom")

    env = _env(tmp_path, [])
    env.tester_provider = dying = DyingProvider()
    env._sleep = lambda s: None  # no real backoff in tests
    try:
        env.call_tester()
        assert False, "should raise"
    except RuntimeError:
        pass
    assert dying.calls == 3
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_env.py -v`
Expected: FAIL — `ModuleNotFoundError: crucible.env`.

- [ ] **Step 4: Implement** — `src/crucible/env.py`

```python
"""The real env behind the loop: subject clone on disk, real mutmut, real providers.

Everything the loop's duck-type promises, wired to the adapters. Retries live here
(the loop treats a raised exception as abort-after-retries).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from crucible.engine import MutmutEngine
from crucible.guardrails import assert_add_only, extract_test_file, test_filename, validate_new_tests
from crucible.loop import RoundReply
from crucible.meter import cost_usd
from crucible.roles import build_critic_prompt, build_tester_prompt
from crucible.runner import run_tests

RETRIES = 3
BACKOFFS = (2, 8)


class SubjectEnv:
    def __init__(self, subject_dir, tester_provider, tester_model, critic_provider,
                 critic_model, module_path, run=subprocess.run):
        self.subject_dir = Path(subject_dir)
        self.tester_provider, self.tester_model = tester_provider, tester_model
        self.critic_provider, self.critic_model = critic_provider, critic_model
        self.module_path = module_path
        self.run = run
        self.engine = MutmutEngine(self.subject_dir, run=run)
        self._sleep = time.sleep

    # --- mutation ---
    def measure(self):
        return self.engine.measure()

    def survivor_diff(self, mid):
        return self.engine.survivor_diff(mid)

    # --- models ---
    def _module_source(self) -> str:
        return (self.subject_dir / self.module_path).read_text()

    def _call(self, provider, model, prompt) -> RoundReply:
        last = None
        for attempt in range(RETRIES):
            try:
                text, usage = provider.complete_with_usage(prompt.system, prompt.user, model=model)
                return RoundReply(text, prompt.prompt_sha256, model, usage)
            except Exception as exc:
                last = exc
                if attempt < RETRIES - 1:
                    self._sleep(BACKOFFS[min(attempt, len(BACKOFFS) - 1)])
        raise RuntimeError(f"model call failed after {RETRIES} attempts: {last}")

    def call_tester(self) -> RoundReply:
        prompt = build_tester_prompt(self.module_path, self._module_source())
        return self._call(self.tester_provider, self.tester_model, prompt)

    def call_critic(self, survivor_diffs) -> RoundReply:
        prompt = build_critic_prompt(self.module_path, self._module_source(), survivor_diffs)
        return self._call(self.critic_provider, self.critic_model, prompt)

    # --- files / guardrails ---
    def write_test_file(self, round_no, arm, content) -> str:
        body = extract_test_file(content) if content.strip().startswith("```") or "```python" in content else content
        rel = Path("tests") / test_filename(round_no, arm)
        (self.subject_dir / rel).write_text(body + "\n")
        status = self.run(["git", "status", "--porcelain"], cwd=str(self.subject_dir),
                          capture_output=True, text=True).stdout
        assert_add_only(status, [str(rel)] + self._known_generated())
        return str(rel)

    def _known_generated(self):
        tests_dir = self.subject_dir / "tests"
        return [str(Path("tests") / p.name) for p in tests_dir.glob("crucible_*_test.py")]

    def validate(self, test_path) -> None:
        validate_new_tests(self.subject_dir, test_path,
                           lambda cwd, test_paths=None, timeout=300:
                           run_tests(cwd, test_paths=test_paths, timeout=timeout, run=self.run))

    def remove_test_file(self, path) -> None:
        (self.subject_dir / path).unlink(missing_ok=True)

    # --- money / provenance ---
    def cost_usd(self, model, usage) -> float:
        return cost_usd(model, usage)

    def head_sha(self) -> str:
        return self.run(["git", "rev-parse", "HEAD"], cwd=str(self.subject_dir),
                        capture_output=True, text=True).stdout.strip()
```

NOTE: `write_test_file` receives RAW model output from the loop; it extracts the fenced block itself (`extract_test_file` raises `GuardrailViolation` → the loop's rejected path). The `content.strip().startswith(...)` guard exists only so unit tests can pass plain content; keep it exactly as written.

- [ ] **Step 5: Run env tests**

Run: `.venv/bin/python -m pytest tests/test_env.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Implement CLI** — `src/crucible/cli.py`

```python
"""crucible CLI. Subcommands: oneshot, harden (report arrives in Task 12).

Plain-ASCII output. Exit codes: 0 = ran to a verdict (clean/dry/cap); 3 = aborted.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from crucible.env import SubjectEnv
from crucible.loop import LoopConfig, harden, oneshot
from crucible.providers_ext import FakeProvider, get_provider
from crucible.receipts import ReceiptWriter


def _provider(name, fake_replies):
    if name == "fake":
        replies = json.loads(Path(fake_replies).read_text()) if fake_replies else []
        return FakeProvider(replies)
    return get_provider(name)


def _cmd_run(args, mode):
    subject = Path(args.subject).resolve()
    tester = _provider(args.tester, args.fake_replies)
    critic = tester if args.critic == args.tester else _provider(args.critic, args.fake_replies)
    if isinstance(tester, FakeProvider) and isinstance(critic, FakeProvider) and critic is not tester:
        critic = tester  # one scripted reply stream for the whole fake run

    env = SubjectEnv(subject_dir=subject, tester_provider=tester, tester_model=args.tester_model,
                     critic_provider=critic, critic_model=args.critic_model,
                     module_path=args.module)
    cfg = LoopConfig(max_rounds=args.rounds, dry_rounds=args.dry_rounds, arm=mode)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.runs_dir) / f"{stamp}-{subject.name}-{mode}"
    writer = ReceiptWriter(run_dir, {
        "subject": str(subject), "module": args.module, "head_sha": env.head_sha(),
        "arm": mode, "tester_model": args.tester_model, "critic_model": args.critic_model,
        "critic_provider": args.critic, "max_rounds": args.rounds,
        "dry_rounds": args.dry_rounds, "started_at": stamp,
    })

    result = oneshot(env, cfg) if mode == "oneshot" else harden(env, cfg)
    for rec in result.rounds:
        writer.append(rec)
    writer.finish(result.verdict, result.total_cost_usd)

    print(f"verdict: {result.verdict}   cost: ${result.total_cost_usd:.4f}")
    for r in result.rounds:
        print(f"  round {r.round} [{r.role:6s}] {r.status:8s} "
              f"kills={len(r.kills):2d} survivors_after={len(r.survivors_after):3d}")
    print(f"receipt: {run_dir}")
    return 3 if result.verdict == "aborted" else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="crucible")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for mode in ("oneshot", "harden"):
        p = sub.add_parser(mode)
        p.add_argument("subject")
        p.add_argument("--module", required=True)
        p.add_argument("--tester", default="anthropic")
        p.add_argument("--tester-model", default="claude-sonnet-5")
        p.add_argument("--critic", default="anthropic")
        p.add_argument("--critic-model", default="claude-sonnet-5")
        p.add_argument("--rounds", type=int, default=5)
        p.add_argument("--dry-rounds", type=int, default=2)
        p.add_argument("--runs-dir", default="runs")
        p.add_argument("--fake-replies", default=None)
    args = parser.parse_args(argv)
    return _cmd_run(args, args.cmd)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Write the end-to-end fixture test** — `tests/test_cli_e2e.py`

```python
"""The integration proof: real mutmut, real pytest, fake model. Marked slow (minutes)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

GOOD_TESTS = """```python
from subject_pkg.calc import acceptance_rate, clamp


def test_clamp_below():
    assert clamp(-1, 0, 10) == 0


def test_clamp_above():
    assert clamp(11, 0, 10) == 10


def test_clamp_inside():
    assert clamp(3, 0, 10) == 3


def test_rate():
    assert acceptance_rate(10, 5) == 0.5


def test_rate_zero_offers():
    assert acceptance_rate(0, 0) == 0.0


def test_rate_negative_offers():
    assert acceptance_rate(-3, 1) == 0.0
```"""


@pytest.mark.slow
def test_oneshot_end_to_end(tmp_path):
    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    # subject package importable by pytest/mutmut inside the crucible venv
    subprocess.run(["python", "-m", "pip", "install", "-q", "-e", str(subject)], check=True)

    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps([GOOD_TESTS]))

    from crucible.cli import main
    rc = main(["oneshot", str(subject), "--module", "subject_pkg/calc.py",
               "--tester", "fake", "--critic", "fake",
               "--fake-replies", str(replies), "--runs-dir", str(tmp_path / "runs")])
    assert rc == 0

    runs = list((tmp_path / "runs").iterdir())
    assert len(runs) == 1
    receipt = (runs[0] / "receipt.jsonl").read_text().strip().splitlines()
    round0 = json.loads(receipt[0])
    assert round0["role"] == "tester" and round0["status"] == "ok"
    result = json.loads((runs[0] / "result.json").read_text())
    assert result["verdict"] in ("clean", "cap", "dry")
```

- [ ] **Step 8: Run the e2e**

Run: `.venv/bin/python -m pytest tests/test_cli_e2e.py -v -m slow`
Expected: 1 PASS (takes 1-3 minutes; mutmut compiles and runs mutants for calc.py). If mutmut errors, debug HERE — this is the task that proves the whole pipe.

- [ ] **Step 9: Full suite + commit**

```bash
.venv/bin/python -m pytest -q
git add src/crucible/env.py src/crucible/cli.py tests/fixtures tests/test_env.py tests/test_cli_e2e.py
git commit -m "feat: real subject env + CLI; offline end-to-end proof on fixture subject"
```

---

### Task 12: `crucible report` — kill matrix, McNemar, cost-per-kill

**Files:**
- Create: `src/crucible/report.py`
- Modify: `src/crucible/cli.py` (add `report` subcommand)
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `receipts.load_run`.
- Produces:
  - `mcnemar_exact(b: int, c: int) -> float` — two-sided exact binomial p-value on discordant pairs (`min(1.0, 2 * sum(comb(n,k) for k<=min(b,c)) / 2**n)` with `n=b+c`; p=1.0 when n=0).
  - `paired_kills(run_a: dict, run_b: dict) -> tuple[int, int, int, int]` — (both, a_only, b_only, neither) over the UNION of baseline survivors (round 0 `survivors_after`) of two runs on the same subject+module; a mutant counts as killed by a run if it appears in any round's `kills`.
  - `summarize(run: dict) -> dict` — `{"arm", "verdict", "baseline_survivors", "killed", "cost_usd", "cost_per_kill"}` (`cost_per_kill = None` when killed == 0).
  - CLI: `crucible report RUN_DIR_A [RUN_DIR_B]` — one run: summary table; two runs: paired 2x2 + McNemar p + per-arm cost-per-kill. Plain ASCII.

- [ ] **Step 1: Write failing tests** — `tests/test_report.py`

```python
import pytest

from crucible.report import mcnemar_exact, paired_kills, summarize


def run_dict(survivors_baseline, kills_by_round, cost=1.0, arm="loop"):
    rounds = [{"round": 0, "role": "tester", "kills": [], "survivors_after": survivors_baseline,
               "cost_usd": 0.5, "status": "ok"}]
    for i, kills in enumerate(kills_by_round, start=1):
        rounds.append({"round": i, "role": "critic", "kills": kills,
                       "survivors_after": [], "cost_usd": 0.5, "status": "ok"})
    return {"meta": {"arm": arm}, "rounds": rounds,
            "result": {"verdict": "dry", "total_cost_usd": cost}}


def test_mcnemar_exact_known_values():
    # b=8, c=2 -> two-sided exact p ~ 0.109375
    assert mcnemar_exact(8, 2) == pytest.approx(0.109375)
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(10, 0) == pytest.approx(2 * (0.5 ** 10), rel=1e-9)


def test_paired_kills_2x2():
    a = run_dict(["m1", "m2", "m3", "m4"], [["m1", "m2"]])
    b = run_dict(["m1", "m2", "m3", "m4"], [["m2", "m3"]])
    both, a_only, b_only, neither = paired_kills(a, b)
    assert (both, a_only, b_only, neither) == (1, 1, 1, 1)


def test_summarize():
    s = summarize(run_dict(["m1", "m2"], [["m1"]], cost=2.0))
    assert s["baseline_survivors"] == 2 and s["killed"] == 1
    assert s["cost_per_kill"] == pytest.approx(2.0)


def test_summarize_zero_kills_has_no_cost_per_kill():
    assert summarize(run_dict(["m1"], [[]]))["cost_per_kill"] is None
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `src/crucible/report.py`

```python
"""Turn receipts into the paper's numbers. Stdlib only; every figure recomputable
by a reader from the receipt files alone.
"""
from __future__ import annotations

from math import comb


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar on discordant pair counts (b: A-only, c: B-only)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def _killed(run: dict) -> set[str]:
    return {m for r in run["rounds"] for m in r.get("kills", [])}


def _baseline(run: dict) -> set[str]:
    for r in run["rounds"]:
        if r["round"] == 0:
            return set(r["survivors_after"])
    return set()


def paired_kills(run_a: dict, run_b: dict) -> tuple[int, int, int, int]:
    union = _baseline(run_a) | _baseline(run_b)
    ka, kb = _killed(run_a), _killed(run_b)
    both = len(union & ka & kb)
    a_only = len((union & ka) - kb)
    b_only = len((union & kb) - ka)
    neither = len(union - ka - kb)
    return both, a_only, b_only, neither


def summarize(run: dict) -> dict:
    killed = len(_killed(run))
    cost = run["result"]["total_cost_usd"] if run["result"] else 0.0
    return {
        "arm": run["meta"].get("arm"),
        "verdict": run["result"]["verdict"] if run["result"] else "incomplete",
        "baseline_survivors": len(_baseline(run)),
        "killed": killed,
        "cost_usd": cost,
        "cost_per_kill": (cost / killed) if killed else None,
    }
```

Add to `cli.py` in `main()` after the run subparsers:
```python
    rp = sub.add_parser("report")
    rp.add_argument("runs", nargs="+")
```
and in the dispatch (replace the final `return _cmd_run(args, args.cmd)`):
```python
    if args.cmd == "report":
        return _cmd_report(args)
    return _cmd_run(args, args.cmd)
```
plus the command:
```python
def _cmd_report(args) -> int:
    from crucible.receipts import load_run
    from crucible.report import mcnemar_exact, paired_kills, summarize

    runs = [load_run(p) for p in args.runs]
    for r in runs:
        s = summarize(r)
        cpk = f"${s['cost_per_kill']:.4f}" if s["cost_per_kill"] is not None else "n/a"
        print(f"{s['arm']:8s} verdict={s['verdict']:6s} baseline={s['baseline_survivors']:3d} "
              f"killed={s['killed']:3d} cost=${s['cost_usd']:.4f} cost/kill={cpk}")
    if len(runs) == 2:
        both, a_only, b_only, neither = paired_kills(runs[0], runs[1])
        p = mcnemar_exact(a_only, b_only)
        print(f"paired 2x2: both={both} a_only={a_only} b_only={b_only} neither={neither}")
        print(f"McNemar exact p = {p:.6f}")
    return 0
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_report.py tests/test_cli_e2e.py -v -m "not slow"` then `.venv/bin/python -m pytest -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/crucible/report.py src/crucible/cli.py tests/test_report.py
git commit -m "feat: report — paired kill matrix, exact McNemar, cost-per-kill"
```

---

### Task 13: Dogfood config + CI + README stub

**Files:**
- Modify: `pyproject.toml` (add `[tool.mutmut]` for crucible's own pure modules)
- Create: `.github/workflows/ci.yml`
- Create: `README.md`

**Interfaces:**
- Produces: CI (unit tests, 3.11/3.12/3.13); local mutation dogfood via `oracle-gate check` on crucible's pure modules; README stating what crucible is, the oracle-gate relationship, and PRIVATE-until-results status.

- [ ] **Step 1: Add dogfood scope to `pyproject.toml`**

```toml
[tool.mutmut]
source_paths = [
    "src/crucible/loop.py",
    "src/crucible/guardrails.py",
    "src/crucible/report.py",
    "src/crucible/meter.py",
    "src/crucible/roles.py",
]
pytest_add_cli_args_test_selection = ["tests/"]
```

- [ ] **Step 2: Write `.github/workflows/ci.yml`**

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v5.0.1
      - uses: actions/setup-python@83679a892e2d95755f2dac6acb1bfd68dd9ad5de # v6.1.0
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: python -m pytest -q -m "not slow"
      - run: python -m pytest -q -m slow
```

NOTE: pin action SHAs per Jeff's CI-hardening standard; verify the SHAs above against the actions' current release tags before committing (they must match real releases — check with `gh api repos/actions/checkout/tags`).

- [ ] **Step 3: Write `README.md`**

```markdown
# crucible

**Status: private until pre-registered results are in.**

Adversarial test-hardening for AI-built code. A Tester agent writes tests; mutation testing
(mutmut) finds the survivors — injected defects no test caught; a Critic agent is handed the
named survivors and writes tests to kill exactly those; the loop runs until dry. Every verdict
is mechanical (pytest kills the mutant or it survives) — no model ever judges model output.

Built on [oracle-gate](https://github.com/Jott2121/oracle-gate): the gate demands evidence,
crucible generates it. Survivor triage, provenance, and cross-model providers are imported
from oracle-gate, not rebuilt. Spend is metered exactly per round (input/output split) via
agent-cost-attribution rates.

## Quickstart

    pip install -e ".[dev]"
    crucible harden /path/to/subject-clone --module pkg/module.py
    crucible report runs/<run-dir>

Design spec: docs/superpowers/specs/2026-07-09-agentic-testing-framework-design.md
Prior art and claims ledger: spec section 1b (MuTAP, AdverTest, Meta ACH).
```

- [ ] **Step 4: Run the dogfood locally**

```bash
cd ~/ai-agentic-code-testing
.venv/bin/python -m pip install -q "oracle-gate[check] @ git+https://github.com/Jott2121/oracle-gate@main#subdirectory=tool"
.venv/bin/oracle-gate check || true   # first run reports; record survivor count in the commit message
```
Expected: a mutation report on crucible's own pure modules. Record the score; do NOT chase survivors yet (that is Task 14's QC pass).

- [ ] **Step 5: Commit and push branch**

```bash
git add pyproject.toml .github README.md
git commit -m "chore: CI matrix, mutation dogfood scope, README"
git push -u origin feat/engine
```

---

### Task 14: Adversarial QC pass (independent review + survivor triage)

**Files:**
- Modify: whatever the review finds (fixes land as individual commits)
- Create: `docs/QC-2026-07.md` (findings log)

**Interfaces:**
- Consumes: the full branch diff `main...feat/engine`.
- Produces: an independent adversarial review (fresh subagent, not the builder), every finding CONFIRMED/refuted with a test or a fix commit; mutation dogfood survivors triaged (killed with new tests, or explained). This is Jeff's standing Builder → QC → fix discipline; the engine is not "done" before this passes.

- [ ] **Step 1: Dispatch an independent reviewer** (fresh subagent; reviews, does not fix)

Review charge: (a) loop semantics vs the spec's §3 contract; (b) guardrail bypasses — can a model output touch source, weaken tests, or fake a kill? (c) receipt completeness — can a reader reconstruct every number? (d) the e2e fixture — does it actually exercise the add-only and validity paths? (e) error paths — aborted rounds, missing keys, dirty subject clones.

- [ ] **Step 2: Reproduce and fix every confirmed finding** (one commit per fix, test-first)

- [ ] **Step 3: Kill or explain mutation survivors on the dogfood scope**

Run: `.venv/bin/oracle-gate check`
Expected: survivors on loop/guardrails/report either killed by new tests (preferred) or explained in `oracle-gate.toml` per oracle-gate's explanation format, digest-bound.

- [ ] **Step 4: Log findings** in `docs/QC-2026-07.md` (finding → verdict → commit), commit.

- [ ] **Step 5: Merge to main**

```bash
git push origin feat/engine
gh pr create --title "crucible engine v0.1" --fill
# after CI green:
gh pr merge --squash
```

---

## After this plan

- **Plan 2 (experiment):** related-work sweep (blocking), `experiments/PROTOCOL.md` pre-registration, `crucible experiment` command (refuses on dirty/uncommitted protocol), subject prep manifests, graph-guard pilot (go/no-go), Claude arms before Jul 12, GPT-5.6 arm, analysis + RESULTS.md.
- **Plan 3 (delivery):** skill wrapper `skill/harden-tests/`, docs polish, public flip with results.

## Self-review notes (completed)

- Spec coverage: engine (§3) Tasks 4-11; guardrails (§4) Task 8 + env wiring Task 11; error handling (§5) Tasks 5/9/11; CLI (§6) Tasks 11-12; testing-crucible-itself (§7) every task + Tasks 13-14; receipts (§3) Task 10; meter (§2 budget row) Task 3; oracle-gate dependency + packaging proof (§2/§3) Tasks 1-2. Experiment (§8) and wrapper (§9) are Plans 2-3 by scope-check design.
- Type consistency: `RoundReply(text, prompt_sha256, model, usage)` defined in loop.py, consumed by env.py. `MutationOutcome(counts, survivors, all_mutants)` defined Task 4, consumed Task 9. `TestRunResult(passed, returncode, output)` Task 5, consumed Task 8/11. `Usage(input_tokens, output_tokens)` from Task 2 everywhere.
- Placeholder scan: gpt-5.6 rate in Task 3 is explicitly marked MUST-verify-before-first-paid-run (that verification is a Plan 2 step, deliberate). CI action SHAs carry an explicit verify instruction. No TBDs remain.
