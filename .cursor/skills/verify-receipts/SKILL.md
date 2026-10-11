---
name: verify-receipts
description: Use before opening or updating a PR, or when README/docs numbers change. Re-runs crucible's lint, tests, and receipt check, cross-checks published experiment numbers against the committed receipts, and writes a receipts block for the PR body.
---
# Verify receipts

1. From the repo root, run the commands in AGENTS.md:
   ```bash
   pip install -e ".[dev]"
   ruff check src tests
   python -m pytest -q -m "not slow" --cov --cov-report=term-missing --cov-fail-under=90
   python -m pytest -q -m slow
   python scripts/check_receipts.py
   ```
   Capture exit codes and the last ~20 lines of each.
   `check_receipts.py` recomputes `experiments/results.json` and `experiments/results-b.json` from the committed receipts (`experiments/analyze.py`, `experiments/analyze_b.py`) and checks README.md, `experiments/RESULTS.md`, and `experiments/RESULTS-B.md` still quote the headline intervals. It does not rewrite those artifacts.
   The `slow` marker shells out to mutmut and takes minutes. Do not deselect it to go green. Do not lower `--cov-fail-under` (90), pyproject `fail_under`, or mutation `fail-under` (`"95"`).
   `integration` tests call live model APIs and are deselected by default. Do not run them in CI.
2. `git diff origin/main -- README.md docs/ experiments/RESULTS.md experiments/RESULTS-B.md paper/` — list every number that changed. For each, re-run `python scripts/check_receipts.py`. If you can't reproduce it, mark it UNVERIFIED and stop; do not open the PR as ready.
3. Grep the diff for employer-data and secret patterns (see `.cursor/rules/40-security-and-data.mdc`). Any hit outside the existing author byline on the paper drafts and the `authors` field in `pyproject.toml` = stop and report.
4. Confirm no thresholds were lowered (`--cov-fail-under`, mutation `fail-under`, pyproject `fail_under`) and no tests were skipped or removed.
5. Output a Markdown block:
   - Commands run + pass/fail
   - Numbers: before → after → command → reproduced? (Y/N)
   - Not verified / known gaps
6. Paste that block into the PR's "How verified" section. Never claim a check passed that you didn't run.
