# crucible

[AGENTS.md](AGENTS.md) is the source of truth for this repo. Cursor, Claude Code, Codex, and cloud agents should read that file before editing.

The operator notes that used to live here are merged into AGENTS.md: what the tool does, `pip install -e ".[dev]"` and `python -m pytest -q`, the narrow `ruff check src tests` gate, the three shipped surfaces (PyPI package `crucible-harden`, the GitHub Action, the Claude Code plugin), the repo-local `.claude/` setup versus the shipped plugin, the two release lines (`pypi-v<version>` versus Action `v1.x`), and the harden-loop constraint that kills must be earned.
