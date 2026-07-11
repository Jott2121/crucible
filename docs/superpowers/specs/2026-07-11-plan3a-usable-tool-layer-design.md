# Design: Plan 3a — the usable-tool layer (Max-plan provider + harden-tests skill)

Date: 2026-07-11
Status: approved (design cockpit approved by Jeff 2026-07-11, "Go")
Build model: sonnet implementers / opus reviewers / Fable orchestrator (son+opus standing default).
Repo: github.com/Jott2121/ai-agentic-code-testing (private until the flip cycle).

## 1. What this is

Make crucible free to run day-to-day and trivial to invoke, so it stops being a science
artifact and becomes a tool someone runs before lunch. Three pieces, one sub-project:

1. **`ClaudeCLIProvider`** — a provider that routes model calls through `claude -p`
   (Claude Code headless) so runs bill Jeff's Max subscription at $0 marginal instead of the
   metered Anthropic API.
2. **`crucible scope`** — a subcommand that automates the setup ritual the experiment did by
   hand: detect the repo layout, write the `[tool.mutmut]` scope, and run the $0 canary
   must-kill probe before any model call.
3. **`harden-tests`** — a thin Claude Code skill, living in-repo at
   `.claude/skills/harden-tests/`, that glues 1+2 into one sentence inside any Claude Code
   session: "harden tests for `<module>`".

**Explicitly out of scope (later cycles):** the public flip (outsider README, repo-sentinel
pass, launch positioning, tool-vs-experiment packaging decision); cross-lineage critics via
CLI; any change to the frozen `experiments/` tree; automating scope setup for arbitrary
stranger repos beyond what the acceptance test needs.

## 2. Acceptance test (the definition of done)

Jeff says "harden tests for `<module>`" in a Claude Code session on one of his real public
portfolio repos (first target: rag-guard or pay-equity-regression, his pick at run time). The
skill runs the full loop on the Max plan — $0 metered spend, verified by the receipt's billing
field — and comes back with:

- generated tests on a **local branch** (never main, PR strictly opt-in),
- a `receipt.jsonl` carrying real token counts, shadow-priced dollars, and
  `billing: "max-plan"`,
- a survivor-triage summary (killed / remaining / dropped-as-wrong-oracle).

This single run, receipts in hand, is gate 6 and closes the plan.

## 3. `ClaudeCLIProvider` (src/crucible/providers_ext.py)

**Decision (cockpit gate, approved):** subprocess `claude -p --output-format json` behind the
existing `Provider` duck-type. Rejected: reusing Claude Code's OAuth token against the API
(ToS-gray, brittle keychain scraping); staying API-only on cheaper models (not $0).

- Implements `complete_with_usage(system, user, model=None)` exactly like the other providers:
  compose system+user into the headless invocation, parse the JSON envelope for the reply text
  and usage (input/output tokens). The loop, env, and guardrails never know the difference —
  the provider seam does all the work (`loop.py`, `guardrails.py` untouched).
- **Task 1 opens with a live envelope probe** (one tiny `claude -p` call, Max-billed, ~$0
  marginal) that records the actual JSON shape in the task notes before any code is written
  against it — the v8 credential-ping discipline applied to an envelope instead of a key.
- Model selection: defaults to the current Sonnet (`claude-sonnet-5` equivalent CLI alias),
  overridable per-invocation. Cheapest-sufficient routing is the caller's job; the provider
  just passes the model through.
- `lineage = "anthropic"`. Registry name: `"claude-cli"`.
- **Truncation detection does not arm for this provider (accepted + documented, cockpit risk
  approved):** there is no request-side `max_tokens` cap to compare against, so no
  `output_cap` attribute is set and `env._call`'s mechanical check is structurally silent
  here. The provider docstring states this plainly, citing the v9 amendment's detection
  asymmetry — disclosed, not silently skipped. The CLI returns complete turns, so the residual
  risk is judged low.
- Errors fail loud: non-zero exit, malformed envelope, or missing `claude` binary raise with
  the stderr tail in the message (same posture as the HTTP providers). The existing env-level
  retry loop applies (transient failures only; there is no truncation class to exempt).
- Timeout: reuse the `request_timeout` pattern (generous, e.g. 1200s — headless runs include
  model queue time).

## 4. Meter + receipts: shadow-price with an explicit billing flag

**Decision (approved):** receipts on Max-plan runs record real token counts, a `cost_usd`
computed at the underlying model's public API rate, and a new `billing` field distinguishing
`"api"` (dollars actually left the account) from `"max-plan"` (plan-covered, shadow-priced).

- `crucible.meter` prices the CLI provider's models by mapping them to their existing API
  rate entries — the fail-closed `UnpricedModel` posture is unchanged (an unknown CLI model
  string still refuses to price).
- `billing` threads: provider declares it (`billing = "max-plan"` class attr; HTTP providers
  default `"api"`), the run records it per role in `meta.json` (`tester_billing`/
  `critic_billing` — a run's role-to-provider mapping is constant, and run-level recording
  keeps `loop.py` untouched per this spec's own artifacts promise; amended 2026-07-11 at
  plan-writing), and
  `report`/`summarize` surface it so a cost-per-kill readout can never silently mix real and
  shadow dollars without the flag being visible. One new field, defaulted to `"api"`
  everywhere legacy, so every existing receipt and test remains valid unmodified.

## 5. Protocol guardrail (gate 3): `crucible experiment` refuses non-API providers

Pre-registered runs demand metered, receipt-exact spend and pinned model ids.
`crucible.experiment` gains a mechanical check: any arm resolving to a provider whose
`billing != "api"` fails closed before any call, with a message naming this spec. This
guardrail is what keeps the day-to-day tool from ever contaminating a future protocol run —
same fail-closed family as `assert_protocol_committed`.

## 6. `crucible scope` (new src/crucible/scope.py + CLI subcommand)

Port the proven logic out of `experiments/validate_scopes.py` (which stays untouched, frozen
with the experiment) into a first-class module:

- **Layout detection:** find the target module; detect src-layout (needs the v7-style
  `conftest.py` sys.path shim) vs package-dir; detect an existing test dir and obvious
  collection hazards (test files importing top-level packages that won't exist in mutmut's
  sandbox -> exclude-form `--ignore=` args, the v6 lesson, mechanized).
- **Scope write:** `[tool.mutmut]` via the existing `engine.write_scope`
  (`create_if_missing=True`), `also_copy` from the detected package dir.
- **Canary must-kill probe ($0, no model):** write a minimal hand-templated test asserting one
  fact read from the module (import succeeds + one public callable runs), confirm it passes
  pristine, run mutmut for real, and require the killed count to strictly increase — the v6
  probe, generalized. A scope that fails the canary refuses to proceed; nothing model-billed
  ever runs against an unproven scope.
- Output: a plain summary (scope written, mutant count, canary delta) the skill can read.
- Honest limitation, stated in `--help` and the skill: heuristics target well-formed Python
  repos with pytest; a repo the canary can't validate is a refusal, not a guess.

## 7. `harden-tests` skill (.claude/skills/harden-tests/SKILL.md, in-repo)

Thin by design — mechanics live in the tested CLI; the skill is instructions, not logic:

1. Preflight: repo is git-clean enough (crucible's own preflight enforces the rest), module
   exists, `.venv`/pytest present; refuse politely otherwise.
2. `crucible scope --module <M>` — if the canary fails, stop and report why.
3. Create/switch to a local branch (`crucible/harden-<module>-<date>`), never main.
4. `crucible harden --module <M> --provider claude-cli` (round cap and dry rules = engine
   defaults).
5. Present the receipt summary: kills, survivors remaining, dropped wrong-oracle tests, token
   counts, shadow cost + `max-plan` flag. Offer — never auto-do — a PR.
6. Guardrails inherited verbatim from repo-sentinel doctrine: local branch only, never main,
   PR strictly opt-in, never on a repo Jeff doesn't own without explicit say-so.

Ships in-repo so the public flip inherits it; Jeff's personal `~/.claude/skills` gets a
symlink so it's invocable everywhere now.

## 8. Testing

TDD throughout; no paid or Max-billed model calls in any test.

- Provider: fake `subprocess.run` returning canned envelopes (shape captured by the task-1
  live probe); error paths (non-zero exit, bad JSON, missing binary); usage parsing; billing
  attr; timeout passed through.
- Meter/receipts: CLI-model pricing maps to API rates; `UnpricedModel` still fails closed;
  `billing` defaults `"api"` on legacy paths; round records and receipt.jsonl carry it.
- Experiment guardrail: a fake provider with `billing="max-plan"` is refused pre-call.
- Scope: fixture mini-repos (src-layout, package-dir, hazard test files) prove detection,
  written scope, and canary verdicts; the existing slow-marked real-mutmut fixture pattern
  covers one true end-to-end canary.
- Skill: the CLI does the work, so the skill file is reviewed (opus) rather than unit-tested;
  the acceptance run (gate 6) is its live test.
- Suites stay green under `-W error`; dogfood mutation score maintained on touched pure
  modules.

## 9. Risks (from the approved cockpit)

- **MED:** `claude -p` envelope shape differs from assumption → task-1 live probe before
  coding (mechanism-check discipline).
- **MED (accepted + documented):** no truncation detection on the CLI provider — no
  mechanical cap exists to check; disclosed in docstring + skill output.
- **LOW:** skill touches Jeff's real repos → repo-sentinel guardrails, local-branch-only.
- **LOW:** build burn — sonnet implementers / opus reviewers per the standing son+opus
  default; Fable only orchestrates.

## 10. YAGNI cuts (recorded)

- No streaming, no session reuse, no multi-turn in the CLI provider — one prompt, one reply.
- No OpenAI/cross-lineage CLI path (H2 closed as null; the API provider still exists for it).
- No auto-PR, no auto-merge, anywhere.
- No stranger-repo scope heuristics beyond what the canary can prove.
- No new receipt schema version — one added field with a safe default.
