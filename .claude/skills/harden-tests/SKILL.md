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

1. Preflight: confirm the target module path exists; the subject repo must be
   committed-clean (`git status --porcelain` empty) with a green suite on
   pristine code -- this is a hard requirement, not a nice-to-have: crucible's
   own preflight refuses (exit non-zero, no tokens spent) on anything less.
   Also confirm the subject's test deps are importable from crucible's venv
   or the subject's own.
2. Branch: `git checkout -b crucible/harden-<module-stem>-<YYYYMMDD>` (never
   reuse an existing branch).
3. Scope + collection gate (free, no model calls):
   `~/ai-agentic-code-testing/.venv/bin/crucible scope <repo> --module <M>`
   -- exit 4 means stop and report the printed reason. Two passing shapes,
   both fine: `canary: KILLS (a -> b of N mutants)` (strict must-kill proof,
   zero-kill baselines) or `canary: WAIVED (existing suite kills K of N
   mutants; collection proven)` (well-tested modules; the waiver is itself
   gated by a pytest-discovery config scan).
   Honest limitation: the scope heuristics target well-formed Python repos
   with pytest; a repo the gate cannot validate is refused, not guessed.
   Disclosure: the strict branch's canary probe may CALL the target module's
   public functions/classes with small dummy arguments on pristine code
   (bounded, deterministic probes; on a pathological module that does I/O or
   mutates state at call time, side effects are possible).
4. Commit the scope config: `crucible scope` writes `pyproject.toml`'s
   `[tool.mutmut]` (and a `conftest.py` shim, for src-layout subjects)
   straight to the working tree, uncommitted. Commit it now, before running
   the loop:
   `git add pyproject.toml; [ -f conftest.py ] && git add conftest.py;
   git commit -m "crucible: scope config for <M>"`
   (`git add` is all-or-nothing on pathspecs: naming a conftest.py that does
   not exist -- every non-src-layout subject -- aborts the whole add and
   stages nothing, so the missing file must be tolerated with a guard, not
   an error redirect). Skipping this step leaves the tree dirty, and step
   5's preflight hard-refuses a dirty tree outright -- receipts also bind
   to a commit sha, so the validated scope needs one to bind to.
5. Run the loop on the Max plan:
   `~/ai-agentic-code-testing/.venv/bin/crucible harden <repo> --module <M>
   --tester claude-cli --critic claude-cli --runs-dir <repo>/.crucible-runs`
6. Commit the accepted `tests/crucible_*_test.py` files to the local branch
   with a message naming kills and the receipt dir.
7. Report, plain ASCII: verdict, kills/baseline survivors, rounds, dropped
   wrong-oracle tests, token totals, shadow cost with the `max-plan` flag
   stated in words ("plan-covered, no metered spend"), receipt path.
   `crucible report` prints `billing=` on every cost line (api / max-plan /
   mixed:...); the underlying fields live in the run dir's `meta.json`
   (`tester_billing`/`critic_billing`). Offer -- do not open -- a PR.

## Refusals

- Dirty repo, missing module, scope exit 4, or `claude` CLI absent: report
  the exact blocker and stop. Never work around a refusal silently.
