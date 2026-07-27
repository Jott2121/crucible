#!/usr/bin/env bash
# Lints the single file an agent just wrote, at the moment it wrote it.
#
# WHY at edit time rather than only in CI: an agent that breaks an import three
# edits ago finds out on the next full test run, having already built on top of
# the break. Feeding the error back immediately keeps the blast radius at one
# file. Exit 2 is the PostToolUse contract for "put stderr in front of Claude";
# the tool has already run by then, so this reports, it never blocks.
#
# Silently no-ops when ruff or jq is missing so a contributor without the dev
# extra installed does not get a hook error on every edit.
set -uo pipefail

command -v ruff >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0

file=$(jq -r '.tool_input.file_path // empty')
[ -n "$file" ] || exit 0

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
rel="${file#"$root"/}"

# Only the packaged tool and its suite. Scratch scripts, experiments/, and the
# docs tree are out of scope for the same reason they are out of scope in CI.
case "$rel" in
  src/*.py | tests/*.py | src/*/*.py | tests/*/*.py) ;;
  *) exit 0 ;;
esac

if ! output=$(cd "$root" && ruff check --no-cache "$rel" 2>&1); then
  printf 'ruff check failed on %s\n\n%s\n' "$rel" "$output" >&2
  exit 2
fi
exit 0
