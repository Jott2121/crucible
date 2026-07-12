# Design: Plan 3b.1 — lean `claude -p` invocation

Date: 2026-07-12
Status: approved (design cockpit approved by Jeff 2026-07-12, "Approve, go" — both defaults: proof
subject = re-harden `rag_guard/guard.py`; lean-as-default with an escape hatch).
Build model: sonnet implementers / opus reviewers / opus orchestrator (Jeff ruled Opus for 3b, per
the son+opus standing default; Fable only via an `ask-fable` consult if a fork needs a frontier read).
Repo: github.com/Jott2121/ai-agentic-code-testing (private until the flip cycle).

## 1. What this is

Every model call crucible makes shells out to `claude -p` (the `ClaudeCLIProvider`,
`src/crucible/providers_ext.py:141`). Today that subprocess is built with **no config-isolation
flags, no `cwd`, and no scrubbed environment**, so it boots a full interactive-equivalent session
that inherits the operator's entire `~/.claude`: every MCP server's tool schemas, every skill
listing, `CLAUDE.md`, and memory. None of that is needed to write a test file.

The gate-7 receipt made the cost visible: **439,230 input / 20,533 output tokens per hardened
module** (`~/.crucible-runs/rag-guard/20260712T050833Z-rag-guard-harden`), a ~1:20
payload-to-overhead ratio. Crucible's own payload — the tester/critic system template (~1.2 KB)
plus the module source inlined into `user` — is only a couple KB. The ~439k is almost entirely
inherited session preload, riding on `cache_read`/`cache_creation` tokens (the same run recorded
`input_tokens=4` for a call whose real cache-borne input was hundreds of thousands of tokens).

This plan strips that dead weight by isolating the subprocess config. The tester/critic calls
return **test code as text and use zero tools**, so the theoretical floor is near-nothing.

**Explicitly out of scope (later 3b cycles):** the public flip (outsider README, repo-sentinel
pass, packaging + launch positioning) — that is Plan 3b item 2; the residual cleanups (tox.ini
`[pytest]` scan, `scope.py` into the dogfood `[tool.mutmut]` scope, `import_hint` threading, exact
`mutmut` pin) — Plan 3b item 3. This spec covers item 1 only. The frozen `experiments/` tree,
`loop.py`, and `guardrails.py` are untouched.

## 2. Acceptance test (the definition of done)

Re-harden `rag_guard/guard.py` — the exact module behind the 439,230 baseline — under lean
invocation, on a throwaway branch discarded after the number is read. The proof passes when the new
run's `receipt`/`meta` shows:

- an **order-of-magnitude input-token reduction** vs 439,230 (target `< ~44,000` input),
- the same functional result the ambient run produced (guard.py baseline survivors still killed —
  a real harden, not a degraded one),
- `billing: "max-plan"`, `$0` metered,
- the isolation rung actually used recorded in `meta.json`.

An independent reviewer (opus) verifies the receipt against the baseline. This apples-to-apples
run, receipts in hand, is the gate that closes item 1.

## 3. The isolation ladder + Task-1 probe (mechanism-check before any code)

**Decision (cockpit gate, approved — "go for the floor"):** aim for the lowest rung that still
authenticates, resolved empirically by a probe *before* any provider code is written against it —
the same task-1 discipline Plan 3a used for the envelope shape. Rejected: "safe-first only" (never
touch `CLAUDE_CONFIG_DIR`, leaving the near-zero floor unclaimed); "minimal, just `--strict-mcp-config`"
(one flag, stop, smallest win).

The isolation ladder, safe → aggressive:

| rung | lever | expected cut | risk |
|------|-------|--------------|------|
| 0 | baseline (current: no flags) | — (the 439k) | none |
| 1 | drop all MCP servers | large (MCP tool schemas are the bulk) | none |
| 2 | + neutral `cwd` (temp dir) | drops project `CLAUDE.md` / project skills | none |
| 3 | + suppress user skills / settings sources | drops skill + settings preload | none |
| 4 | + isolated minimal `CLAUDE_CONFIG_DIR` | the floor (near-nothing) | **may break Max auth** |

**Task 1 is a standalone probe script** (`scripts/` or `tools/`, throwaway-grade, not wired into
the provider), independent of the provider so it genuinely precedes provider code. It shells out
`claude -p` with a trivial prompt ("reply with the literal string OK") under each rung and records,
per rung:

- **auth-ok?** — did the call authenticate at all,
- **completion-ok?** — did a well-formed result envelope come back with the expected text,
- **input tokens** — parsed from the same envelope `usage` fields the provider already reads
  (`input + cache_creation + cache_read`).

The probe's output is a measured rung table. It is cheap ($0 metered, pennies of shadow cost) and it
**resolves two unknowns empirically**: (a) which levers actually move the token count and by how
much — we do not trust the flag names or the "MCP is the bulk" hypothesis until the numbers show it;
(b) for rung 4, whether Max-plan auth survives an isolated `CLAUDE_CONFIG_DIR`, and if it needs any
credential material present in the pinned dir (e.g. a copied `0600` credentials file) vs. authing
from the macOS keychain regardless. Exact CLI flag names are treated as candidates the probe
verifies, not facts — the probe is the source of truth the provider is then coded against.

## 4. Provider isolation knobs (`src/crucible/providers_ext.py`)

**Decision (approved):** extend `ClaudeCLIProvider` to build its subprocess from an explicit
isolation profile, defaulting to the winning rung the probe selected. Rejected: scattering raw flag
strings through `complete_with_usage`.

- A small dataclass — `LeanProfile` (levers: `strict_mcp: bool`, `config_dir: Path | None`,
  `cwd: Path | None`, `setting_sources: str | None`, plus whatever additional lever the probe proves
  necessary) — carries the isolation intent. A pure factory turns a profile into the concrete
  `(argv_extension, env_overrides, cwd)` triple. This is the deep seam: the profile is the interface,
  the flag/env mechanics are the hidden internals, and the factory is unit-testable in isolation.
- `complete_with_usage` composes the base argv (`claude -p --output-format json --model … --system-prompt …`,
  user still via stdin — unchanged) with the profile's `argv_extension`, passes `env=` (ambient env
  merged with the profile's overrides) and `cwd=` to `self._run`. The injected-`run` seam and the
  envelope parsing (`_extract_result`, cache-token summing at lines 161-164) are unchanged.
- The **minimal config dir** (rung 4) is generated **ephemerally at runtime** in a temp dir —
  nothing committed or stale to rot. Its contents are exactly what the probe proved auth needs (most
  likely just a copied `0600` credential file, or empty if auth is keychain-borne), plus a minimal
  settings that loads no MCP, no skills, no `CLAUDE.md`. The temp dir is cleaned up after the run.
- The **neutral cwd** is a temp dir (or the run dir) so no project-level `CLAUDE.md` or project
  skills are discovered by the subprocess.

## 5. Lean-as-default, escape hatch, and a bounded runtime fallback

**Decision (approved default):** because the tester/critic calls use zero tools, lean-isolated is the
**default** invocation path.

- **Escape hatch:** an env var (`CRUCIBLE_LEAN=0`) forces the ambient rung-0 invocation, for
  debugging and for A/B measurement against the 439k baseline. Documented in the provider docstring
  and surfaced in `--help`.
- **Bounded runtime fallback (honors the approved cockpit risk):** if the configured rung fails with
  an **auth-class** error (distinguished from a genuine model/transport error by the stderr/envelope
  signature the probe characterizes), the provider falls back to **the safest probe-validated rung**
  (the lowest-token rung the probe proved authenticates with zero auth risk), retries **once**, and
  records the rung actually used. It does not build a
  full multi-rung retry cascade — a single characterized fallback is enough to survive a stale-auth
  blip; anything more is a YAGNI cut. A non-auth error still fails loud with the stderr tail (posture
  unchanged from 3a). If even the fallback rung fails auth, fail loud with an actionable message
  ("re-run the isolation probe or set `CRUCIBLE_LEAN=0`").

## 6. Receipts + meta: record the rung used

**Decision (approved):** every run records which isolation rung actually served each model call, so
the token win is self-documenting and an auth fallback is never silent.

- Following Plan 3a's billing precedent (record at the run level to keep `loop.py` untouched per the
  artifacts promise), `meta.json` gains a `lean_isolation` field stamped in `cli.py` alongside the
  existing `tester_billing`/`critic_billing` — naming the configured rung and, if the runtime
  fallback fired, the rung actually used. One new field, defaulted to a legacy-safe value (e.g.
  `"ambient"`), so every existing receipt and test stays valid unmodified.
- `RoundRecord` (`loop.py:48-65`) and `receipt.jsonl` are **not** changed — `loop.py` stays frozen.
  The per-round `usage_in` already carries the (now much smaller) combined input count; the meta
  field explains why it shrank.

## 7. Testing

TDD throughout; **no paid or Max-billed model call in any test** (the probe and the proof run are
operator-run, not part of the suite).

- **Profile factory:** pure unit tests — a given `LeanProfile` produces the exact expected
  `(argv_extension, env_overrides, cwd)`. This is where the flag/env mechanics are pinned.
- **Provider:** the existing fake-`run` injection (`tests/test_providers_ext.py`) extended to assert
  the subprocess is built with the profile's argv, `env`, and `cwd` — **none of which any current
  test pins** (today's tests assert argv and stdin only). Add: escape-hatch forces rung 0; auth-class
  error triggers exactly one fallback and records the rung; non-auth error still fails loud.
- **Ephemeral config dir:** a test proves the temp dir is created with the intended minimal contents
  and cleaned up, using a fake filesystem/temp path — no real `claude` binary, no real credentials.
- **Meta:** `lean_isolation` defaults to the legacy-safe value on ambient/legacy paths; a lean run
  records the configured rung; a fallback records the served rung.
- Suites stay green under `-W error`; dogfood mutation score maintained on touched pure modules
  (the profile factory is a prime dogfood target).

## 8. Risks (from the approved cockpit)

- **HIGH (probed, not assumed):** isolated `CLAUDE_CONFIG_DIR` may break Max auth. Task-1 probe
  resolves it cheaply before any code depends on it; bounded runtime fallback + escape hatch cover a
  later stale-auth blip; the served rung is recorded honestly in meta.
- **MED (accepted):** flag names / "MCP is the bulk" are hypotheses — the probe is the source of
  truth; the provider is coded against measured rungs, not assumed ones.
- **MED (resolved by Jeff at design gate):** proof subject = re-harden `rag_guard/guard.py`
  (apples-to-apples vs the 439k baseline), throwaway branch discarded.
- **LOW:** lean-as-default changes behavior for existing callers — mitigated by the `CRUCIBLE_LEAN=0`
  escape hatch and the recorded rung, so a run's isolation is always visible and reversible.

## 9. YAGNI cuts (recorded)

- No multi-rung retry cascade — one characterized auth fallback, then fail loud.
- No committed/persistent minimal config dir — generated ephemerally per run, cleaned up.
- No change to `loop.py` / `RoundRecord` / `receipt.jsonl` schema — one meta field, safe default.
- No streaming, no session reuse — unchanged from 3a (one prompt, one reply).
- No touching the frozen `experiments/` tree, `guardrails.py`, or the scope/skill layers — item 1 is
  the provider invocation and its receipt, nothing else.
