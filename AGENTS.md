# AGENTS.md — crucible

> Portable agent instructions. Read by Cursor (local + cloud agents), Claude Code (via CLAUDE.md), Codex, and Grok Bot cloud-agent runs.
> Keep this file under ~150 lines. Procedures live in `.cursor/skills/`, scoped rules in `.cursor/rules/*.mdc`, review rules in `.cursor/BUGBOT.md`.

## What this repo is
Mutation-testing tool that answers "your AI wrote the tests, who tested the tests?" It injects real defects into a module, measures how many that module's own suite kills, then runs a harden loop where a Critic writes tests against the named survivors. Verdicts are mechanical (pytest kills the mutant or it survives). No model grades model output.

Headline Experiment 2 number: the critic loop killed a mean **0.783** of the survivors a frozen round-0 left standing (95% cluster-bootstrap interval **[0.592, 0.935]**). Experiment 1: the loop arm had **105** discordant kills to **0** (pooled exact McNemar p = **4.9×10⁻³²**). Reproduce both with `python scripts/check_receipts.py` (recomputes `experiments/results.json` and `experiments/results-b.json` from the committed receipts and checks the write-ups still quote them). Full tables: `experiments/RESULTS-B.md`, `experiments/RESULTS.md`.

- **Status:** active · **License:** MIT · **Package:** `crucible-harden` (console script: `crucible`)
- **Ships:** the PyPI package, the GitHub Action (`action.yml`, `uses: Jott2121/crucible@v1`), and a Claude Code plugin
- **Entry points:** `src/crucible/`, `tests/`, `experiments/`, `skills/harden-tests/`, `.claude-plugin/`, `action.yml`
- **Part of:** the governed-agent stack (rag-guard · graph-guard · agent-gate · crucible · oracle-gate · agent-cost-attribution · bow · fleet-mode)

## Commands
```bash
pip install -e ".[dev]"          # or: uvx --from crucible-harden crucible score ... (no install, published CLI only)
ruff check src tests             # lint gate. Narrow on purpose (pyproject.toml). Format is not enforced.
python -m pytest -q -m "not slow" --cov --cov-report=term-missing --cov-fail-under=90
python -m pytest -q -m slow      # mutmut; minutes. Do not deselect it to go green.
python scripts/check_receipts.py # recomputes published experiment figures; does not rewrite them
```
No mypy gate. A task is not done until `ruff check src tests` and the pytest commands pass and the output is pasted in the PR. When a published number changes, `check_receipts.py` must pass too.

`python experiments/analyze.py` and `python experiments/analyze_b.py` rewrite `experiments/results.json` and `experiments/results-b.json`. Prefer `check_receipts.py`, which compares in memory.

## Non-negotiables
1. **No employer data. Ever.** Personal work on personal equipment. Never add, paste, paraphrase, or "anonymize" anything from Lockheed Martin systems, documents, tickets, chats, or datasets. No employer names in fixtures, no internal acronyms, no realistic HR records. Synthetic data only. If a prompt looks like it came from work, stop and ask.
2. **Receipts over hype.** Every number in README, docs, PR descriptions, or posts must be reproducible from a committed command. Link the command and the artifact (`experiments/runs/`, `experiments/runs-b/`, CI log).
3. **Honest benchmarks.** Report nulls and regressions at the same prominence as wins. State n, seeds, model + version, date, and cost. Protocols are `experiments/PROTOCOL.md` and `experiments/PROTOCOL-B.md`, frozen before the runs. Never tune on the test set. Never delete an inconvenient run; mark it superseded with a reason.
4. **Fail closed.** Gates, validators, and guards deny on error, timeout, missing input, or unparseable output. Never weaken a guard to make a test pass. Never catch-and-ignore exceptions in a decision path.
5. **Tests and CI are the definition of done.** New behavior ships with a test that fails without it. Bug fixes ship with a regression test. Do not lower `--cov-fail-under` (90), pyproject `fail_under`, or the mutation workflow's `fail-under` (`"95"`). Do not mark tests `skip`/`xfail` to get green.
6. **Model never grades its own output.** Prefer mechanical verdicts. Where a judge model is needed, use a different lineage from the author and record both. Providers are `anthropic`, `openai`, and `claude-cli` (via oracle-gate). There is no xAI client.
7. **Irreversible = human-gated.** No force-push, no history rewrite, no publishing to PyPI, no tagging releases, no posting. Open a PR; a human merges. Harden runs only on command, not autonomously.

## Code style
- Python >=3.11 (`requires-python`). Stdlib-first. Every new runtime dependency needs a one-line justification in the PR. `mutmut` is pinned exactly (`==3.7.0`) because the canary and the engine depend on internals.
- Type hints on public functions. Small pure functions. No global mutable state.
- Errors: raise specific exceptions; no bare `except`.
- Secrets only via env vars (`ANTHROPIC_API_KEY` and friends). `.env` is gitignored; never print secret values.
- Don't commit `__pycache__/`, `*.pyc`, `.coverage`, `.venv/`, `mutants/`, or `.cursor/hook-logs/`.

## How to work in this repo
- Start non-trivial work in Plan mode; save the plan to `.cursor/plans/` and link it in the PR.
- Default to one agent. Fan out only for read-heavy, independent work. Writes stay single-threaded per file.
- Keep PRs small (< ~400 changed lines) with one intent. Title: `type(scope): summary`.
- PR body: **What / Why / How verified (commands + output) / Numbers changed (before → after, with command) / Risks / Not done**.
- When you learn something durable, propose an edit to this file or a skill in the same PR.
- crucible is intentionally not an MCP server. `.cursor/mcp.json` is the agent's Context7 and agent-gate config, not a crucible tool.

## Directory map
- `src/crucible/` — CLI, loop, score, scope, meter, providers, prompts
- `tests/` — suite (462 collected). `slow` shells out to mutmut; `integration` calls live APIs and is deselected by default, including in CI
- `experiments/` — frozen protocols, receipts (`runs/`, `runs-b/`, `seeds/`), `analyze.py`, `analyze_b.py`, `RESULTS.md`, `RESULTS-B.md`
- `paper/` — manuscript drafts. Author byline only; do not add employer material
- `docs/` — `MUTATION.md`, `RELATED-WORK.md`, demo assets, `superpowers/` plans and specs
- `scripts/` — probes and `check_receipts.py`
- `skills/harden-tests/` — operator ritual, shipped as the plugin. `.claude-plugin/` holds the manifests
- `.claude/` — repo-local Claude Code settings, ruff hook, `/release` skill. Does **not** ship in the plugin
- `.cursor/` — rules, Bugbot, hooks, MCP, `verify-receipts` skill
- `action.yml` — GitHub Action. `.github/workflows/` — ci, CodeQL, mutation badge, PyPI publish, Dependabot

## Known traps
- **Two release lines.** PyPI tags must be `pypi-v<version>` (`publish.yml` is gated on that prefix and the build asserts the tag matches `pyproject.toml`). Action releases stay `v1.x`. A package tag `v0.1.2` publishes nothing. Cut releases with `.claude/skills/release/SKILL.md`. The trigger is a published GitHub Release, not a pushed tag. `.claude/settings.json` asks before edits to `publish.yml` or `action.yml`.
- **Shell guard.** The `beforeShellExecution` matcher includes `git pull`, so `git pull --rebase` and `git pull -r` reach `.cursor/hooks/guard-shell.sh` and are denied. A plain `git pull` is allowed. The script also denies force-push, `reset --hard`, `git tag`, `twine upload`, `uv publish`, `gh release`, and a payload whose `command` is missing, blank, or not a string. Invalid JSON exits non-zero and the hook fails closed. `git push` and `curl`/`wget` ask. Pipe-to-shell is denied.
- **Kills must be earned.** The harden loop discards Critic-written tests that fail on pristine code. Do not bank an unearned kill.
- **Frozen receipts.** Do not edit files under `experiments/runs/`, `experiments/runs-b/`, or `experiments/seeds/`. Supersede with a new run and a note. The Cursor format hook does not rewrite those trees.
- **`tests/test_packaging.py`** guards metadata PyPI validates but `twine check` does not, and CI must run the lowest Python `requires-python` claims (3.11).
- **Mutation badge.** `mutation.yml` force-pushes `refs/heads/badges` on main only. Agents do not run that push.
- **Ruff is a correctness gate, not a formatter.** Selected rules are E and F, ignoring E501, E401, E402, and E741. Do not reflow the tree to satisfy a column count.
- **No Grok integration rule.** This repo does not call the xAI API. `.cursor/rules/60-grok-integration.mdc` is intentionally absent.
