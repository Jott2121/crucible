"""The shell guard must see rebasing pulls and reject unusable command payloads."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / ".cursor" / "hooks" / "guard-shell.sh"
HOOKS = ROOT / ".cursor" / "hooks.json"


def _run(payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(GUARD)],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )


def _permission(payload: object) -> str:
    result = _run(json.dumps(payload))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["permission"]


def test_matcher_includes_git_pull():
    hook = json.loads(HOOKS.read_text(encoding="utf-8"))
    matcher = hook["hooks"]["beforeShellExecution"][0]["matcher"]
    assert "git pull" in matcher.split("|")
    assert hook["hooks"]["beforeShellExecution"][0]["failClosed"] is True


def test_plain_pull_allowed_and_rebasing_pull_denied():
    assert _permission({"command": "git pull"}) == "allow"
    assert _permission({"command": "git pull origin main"}) == "allow"
    for command in (
        "git pull --rebase",
        "git pull --rebase origin main",
        "git pull origin main --rebase",
        "git pull -r",
        "git pull -r origin main",
        "  git pull --rebase  ",
    ):
        assert _permission({"command": command}) == "deny", command


def test_unusable_command_is_denied():
    for payload in (
        {},
        {"cwd": "/tmp"},
        {"command": ""},
        {"command": "   "},
        {"command": None},
        {"command": 1},
        {"command": ["git", "pull"]},
    ):
        assert _permission(payload) == "deny", payload


def test_invalid_json_exits_nonzero():
    result = _run("{")
    assert result.returncode != 0


def test_rewrite_flags_are_denied_in_any_position():
    for command in (
        "git push --force",
        "git push origin --force",
        "git push origin main --force",
        "git push -f",
        "git push origin -f",
        "git push origin HEAD:main -f",
        "git push -uf origin HEAD",
        "git push --force-with-lease",
        "git push origin --force-with-lease",
        "git push origin --force-with-lease=main",
        "git reset --hard",
        "git reset --hard HEAD",
        "git reset HEAD --hard",
    ):
        assert _permission({"command": command}) == "deny", command
    assert _permission({"command": "git push"}) == "ask"
    assert _permission({"command": "git push origin main"}) == "ask"
    assert _permission({"command": "git reset --soft HEAD"}) == "allow"
    assert _permission({"command": "git reset HEAD"}) == "allow"
