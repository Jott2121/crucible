---
name: harden-tests
description: Use when the operator asks to "harden tests" for a module/repo -- runs crucible's adversarial test-hardening loop (Tester -> mutation testing -> Critic on named survivors) onto a LOCAL branch, with mutation-kill receipts. On a Claude subscription the model calls are plan-covered; with an API key they cost real money. Triggers: "harden tests", "harden the tests for X", "run crucible on X", "mutation-harden".
---

# harden-tests

Runs crucible's adversarial test-hardening loop against one module of the
current repo. Verdicts are mechanical (pytest kills the mutant or it
survives); receipts land in a run directory; generated tests land on a local
branch.

## Read this before the first run

**The loop writes tests and then executes them.** The Tester and Critic are
language models; their output is Python that pytest runs on your machine, in
your working tree, with your environment and credentials. crucible constrains
what lands (add-only, and any test that fails on pristine code is discarded)
but it does not sandbox execution. Run it on code you would run a dependency's
test suite for, and read the diff before you merge it.

**Cost depends on how you invoke it.** With `--tester claude-cli --critic
claude-cli` the calls go through Claude Code headless on your Claude
subscription: no metered spend, and receipts are shadow-priced and flagged
`billing: max-plan`. With `--tester anthropic` (or any API provider) the same
run bills your `ANTHROPIC_API_KEY` at real rates. The dollar figure crucible
prints is a *shadow price* under a subscription and an *actual charge* under an
API key -- `crucible report` prints `billing=` on every cost line so the two are
never confused. Reference point: a small module cost about $0.05 shadow-priced
over four rounds. A large module with many survivors costs materially more, and
`--rounds` bounds it.

**Requirements**
- The `claude` **binary** on PATH and logged in, for `claude-cli` providers.
  A shell alias or function is not enough: crucible spawns a subprocess, which
  never sees shell functions. Check with `python -c "import shutil;
  print(shutil.which('claude'))"`, not with `which claude` in an interactive
  shell.
- `crucible` on PATH: `pip install crucible-harden` (>= 0.1.1). The
  distribution is `crucible-harden`; the command it installs is `crucible`.
- A git-clean subject repo. A repo with no `.gitignore` will go dirty with
  `__pycache__` the moment anything runs pytest, and the preflight then
  refuses -- correctly. Add one first.
- Python 3.11+.

## Hard guardrails (non-negotiable)

- LOCAL branch only. Never commit to main. Opening a PR is strictly opt-in
  (ask; never assume).
- Only on repos the operator owns or explicitly names. Never mutate the
  upstream: crucible runs in the working clone, add-only for tests.
- If the scope step refuses (exit 4), STOP and report the printed reason --
  never hand-tune the scope to force a pass. A scope the gate cannot prove is
  a scope that silently loses kills: mutmut reports "no mutants survived" just
  as happily when the tests never ran at all, so an unproven scope can look
  like a perfect score.
- Never present a shadow price as a bill, or a bill as free. State which one
  it is, in words.

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
   `crucible scope <repo> --module <M>`
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

   ```sh
   git add pyproject.toml
   [ -f conftest.py ] && git add conftest.py
   git commit -m "crucible: scope config for <M>"
   ```

   (POSIX shell; on Windows use the equivalent, or run under WSL/Git Bash --
   crucible itself is cross-platform but these snippets are not.) `git add` is
   all-or-nothing on pathspecs: naming a `conftest.py` that does not exist --
   every non-src-layout subject -- aborts the whole add and stages nothing, so
   the missing file must be tolerated with a guard, not an error redirect.
   Skipping this step leaves the tree dirty, and step 5's preflight
   hard-refuses a dirty tree outright -- receipts also bind to a commit sha,
   so the validated scope needs one to bind to.
5. Run the loop:

   ```sh
   crucible harden <repo> --module <M> \
     --tester claude-cli --critic claude-cli \
     --runs-dir ~/.crucible-runs/<owner>-<repo-name>
   ```

   The runs dir must live OUTSIDE the repo: receipts written inside the
   subject tree show up as untracked files and trip crucible's own add-only
   guardrail mid-run (the CLI now refuses an inside-repo runs-dir outright).
   Include the owner in the directory name -- `<repo-name>` alone collides for
   same-basename repos from different owners, and receipts from two projects
   in one directory are worse than useless.
   Bound the spend with `--rounds` if the module is large; the default is 5,
   and each round is one Tester or Critic call plus a full mutmut pass.
6. Commit the accepted `tests/crucible_*_test.py` files to the local branch
   with a message naming kills and the receipt dir. Read them first: they are
   model-written tests and they are about to become part of the suite that
   defines correctness for this module.
7. Report, plain ASCII: verdict, kills/baseline survivors, rounds, dropped
   wrong-oracle tests, token totals, and cost with the billing mode stated in
   words -- "plan-covered, no metered spend" for `max-plan`, or "billed to your
   API key" for `api`. Give the receipt path. `crucible report` prints
   `billing=` on every cost line (api / max-plan / mixed:...); the underlying
   fields live in the run dir's `meta.json` (`tester_billing`/`critic_billing`).
   Offer -- do not open -- a PR.

## Refusals

- Dirty repo, missing module, scope exit 4, or the `claude` binary absent:
  report the exact blocker and stop. Never work around a refusal silently.
