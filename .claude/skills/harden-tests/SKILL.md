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
- If the scope step refuses (exit 4), STOP and report the printed reason --
  never hand-tune the scope to force a pass; a scope the gate cannot prove
  is a scope that silently loses kills (the v6 lesson this gate exists for).
- Requires: `claude` CLI on PATH (logged in), crucible's venv
  (`~/ai-agentic-code-testing/.venv`), a git-clean subject repo.

## Procedure

1. Preflight: confirm the target module path exists; `git status` clean
   enough (crucible's own preflight enforces committed-clean and green
   suite); confirm the subject's test deps are importable from crucible's
   venv or the subject's own.
2. Branch: `git checkout -b crucible/harden-<module-stem>-<YYYYMMDD>` (never
   reuse an existing branch).
3. Scope + collection gate (free, no model calls):
   `~/ai-agentic-code-testing/.venv/bin/crucible scope <repo> --module <M>`
   -- exit 4 means stop and report the printed reason. Two passing shapes,
   both fine: `canary: KILLS (a -> b of N mutants)` (strict must-kill proof,
   zero-kill baselines) or `canary: WAIVED (existing suite kills K of N
   mutants; collection proven)` (well-tested modules; the waiver is itself
   gated by a pytest-discovery config scan).
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

- Dirty repo, missing module, scope exit 4, or `claude` CLI absent: report
  the exact blocker and stop. Never work around a refusal silently.
