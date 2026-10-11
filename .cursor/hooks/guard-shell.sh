#!/usr/bin/env bash
# beforeShellExecution guard. Reads {"command": "...", "cwd": "..."} on stdin.
# Denies irreversible / publishing commands; asks on network fetches.
# Invalid JSON exits non-zero so hooks.json failClosed denies the command.
# A well-formed payload with a missing, blank, or non-string command is denied.
# The matcher includes `git pull`, so `git pull --rebase` reaches this script.
# A plain `git pull` is allowed; a rebasing pull is denied.
set -euo pipefail
input="$(cat)"
status=0
cmd="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    payload = json.load(sys.stdin)
except json.JSONDecodeError:
    raise SystemExit(1)
if not isinstance(payload, dict):
    raise SystemExit(2)
command = payload.get("command")
if not isinstance(command, str) or not command.strip():
    raise SystemExit(2)
sys.stdout.write(command.strip())
')" || status=$?
deny() { printf '{"permission":"deny","user_message":"%s","agent_message":"%s Open a PR instead; a human will do this step."}\n' "$1" "$1"; exit 0; }
ask()  { printf '{"permission":"ask","user_message":"%s"}\n' "$1"; exit 0; }
if [ "$status" -eq 2 ]; then
  deny "Empty or non-string command blocked by repo policy."
elif [ "$status" -ne 0 ]; then
  exit "$status"
fi
# `git pull -r` is rebase. Combined short options (for example `-rv`) count.
# `--rebase` is caught by the substring check below.
pull_short_rebase=0
case "$cmd" in
  *"git pull"*)
    for token in $cmd; do
      case "$token" in
        -r) pull_short_rebase=1 ;;
        -[!-]*)
          case "${token#-}" in
            *r*) pull_short_rebase=1 ;;
          esac
          ;;
      esac
    done
    ;;
esac
if [ "$pull_short_rebase" -eq 1 ]; then
  deny "History rewrite blocked by repo policy."
fi
# Flag position does not matter: `git push origin --force` and
# `git reset HEAD --hard` are the same bans as `git push --force` and
# `git reset --hard`. Combined shorts such as `-uf` count as `-f`.
saw_push=0
saw_reset=0
force_flag=0
hard_flag=0
for token in $cmd; do
  case "$token" in
    push) saw_push=1 ;;
    reset) saw_reset=1 ;;
    --force*) force_flag=1 ;;
    --hard) hard_flag=1 ;;
    -f) force_flag=1 ;;
    -[!-]*)
      case "${token#-}" in
        *f*) force_flag=1 ;;
      esac
      ;;
  esac
done
if [ "$saw_push" -eq 1 ] && [ "$force_flag" -eq 1 ]; then
  deny "Force-push blocked by repo policy."
fi
if [ "$saw_reset" -eq 1 ] && [ "$hard_flag" -eq 1 ]; then
  deny "History rewrite blocked by repo policy."
fi
case "$cmd" in
  *"rebase"*) deny "History rewrite blocked by repo policy." ;;
  *"git tag"*|*"twine upload"*|*"uv publish"*|*"gh release"*) deny "Releases/publishing are human-only." ;;
  *"rm -rf /"*|*"rm -rf ~"*|*'rm -rf $HOME'*)         deny "Destructive delete blocked." ;;
  *"curl"*"| sh"*|*"curl"*"| bash"*|*"wget"*"| sh"*)   deny "Pipe-to-shell blocked." ;;
  *"git push"*)                                       ask  "Agent wants to push a branch. Allow?" ;;
  *"curl"*|*"wget"*)                                  ask  "Agent wants network access: $cmd" ;;
esac
printf '{"permission":"allow"}\n'
