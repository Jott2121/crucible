#!/usr/bin/env bash
# afterFileEdit (notification-only): lint an edited product Python file and warn on
# employer-data / secret patterns. It can't block the edit; CI's no-employer-data job is the real gate.
#
# crucible CI runs `ruff check src tests` and does not enforce `ruff format`.
# Frozen receipts under experiments/runs, experiments/runs-b, and experiments/seeds
# must never be rewritten, so this hook does not format or autofix.
set -uo pipefail
f="$(python3 -c 'import sys,json; print(json.load(sys.stdin).get("file_path",""))')"
[ -f "$f" ] || exit 0

root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
rel="${f#"$root"/}"
case "$rel" in
  src/*.py|tests/*.py)
    if command -v ruff >/dev/null; then
      ruff check -q "$f" || true
    fi
    ;;
esac

# Employer terms (hashed) and export-control markers come from the same scanner
# CI runs; a scanner error counts as a hit. A warning in the hook log is still useful.
if ! python3 "$root/scripts/scan_blocked_terms.py" "$f" >/dev/null 2>&1 \
   || grep -EIq 'BEGIN (RSA|OPENSSH) PRIVATE KEY|xai-[A-Za-z0-9]{20,}' "$f"; then
  mkdir -p .cursor/hook-logs
  echo "$(date -u +%FT%TZ) WARN employer/secret pattern in $f" >> .cursor/hook-logs/warnings.log
fi
exit 0
