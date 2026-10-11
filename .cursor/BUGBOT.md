# .cursor/BUGBOT.md — review rules for crucible
# (Bugbot does NOT read .cursor/rules/*.mdc; it reads this file.)

Flag as **blocking**:
1. Any guard, gate, validator, or refusal path that now fails OPEN (returns allow/True/answer on exception, timeout, empty, or malformed input).
2. Lowered thresholds: `--cov-fail-under`, pyproject `fail_under`, mutation `fail-under` in `.github/workflows/mutation.yml`, retry/timeout bounds removed.
3. Tests that were deleted, skipped, xfailed, or had assertions weakened without a stated reason in the PR body.
4. README, `experiments/RESULTS*.md`, or `paper/` numbers that changed without a reproducing command (`python scripts/check_receipts.py`) or artifact in the PR.
5. Any content that looks like employer/corporate data: company names (Lockheed, LM, LMCO), internal acronyms, CUI/ITAR markings, real-looking employee records, internal URLs. The author byline on the paper drafts is the existing identification; do not add employer material anywhere else. This repo is personal work only.
6. Secrets, tokens, `.env` files, or absolute personal paths committed.
7. Unpinned GitHub Actions (must be full SHA) or widened workflow `permissions:`.
8. Live network / model calls added to the default test path (`integration` must stay deselected).
9. Edits to frozen receipts under `experiments/runs/`, `experiments/runs-b/`, or `experiments/seeds/`.
10. A package release tag that is not `pypi-v<version>`, or an agent edit that publishes to PyPI.

Flag as **non-blocking**:
- New runtime dependency without justification.
- Non-deterministic code in eval paths (unseeded RNG, unordered iteration in hashes/output).
- Exceptions swallowed in non-decision code.

Do not comment on: formatting handled by ruff; naming bikesheds. Ruff format is not a CI gate.
