#!/usr/bin/env python3
"""Isolation probe (Plan 3b.1 Task 1, mechanism-check). Measures input-token
cost and auth survival of `claude -p` under escalating config isolation.
Throwaway grade: run it, read the table, record the winning rung in
docs/superpowers/PROBE-RESULTS-3b.md. Not imported by the package. $0 metered
(Max plan); a handful of trivial calls.

CLI 2.1.207 flags (grounded via `claude --help`):
  --strict-mcp-config      only MCP from --mcp-config; with none => zero MCP.
  --setting-sources <s>    comma list of {user,project,local}; empty => none
                           (drops skills, CLAUDE.md, plugins, hooks). Auth is
                           handled separately, so this should NOT break login.
"""
import json
import os
import subprocess
import tempfile

MODEL = "claude-sonnet-5"
SYSTEM = "You are a probe. Reply with exactly: OK"
USER = "Reply with exactly: OK"

AUTH_MARKERS = ("login", "unauthor", "authenticat", "not logged in", "invalid api key",
                "credential")


def _run(extra_argv, env_overrides, cwd):
    cmd = ["claude", "-p", "--output-format", "json", "--model", MODEL,
           "--system-prompt", SYSTEM] + extra_argv
    env = dict(os.environ)
    env.update(env_overrides)
    try:
        proc = subprocess.run(cmd, input=USER, capture_output=True, text=True,
                              timeout=300, env=env, cwd=cwd)
    except Exception as exc:  # missing binary, timeout
        return {"auth_ok": False, "done": False, "input": None, "note": repr(exc)[:70]}
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-300:]
        is_auth = any(m in tail.lower() for m in AUTH_MARKERS)
        return {"auth_ok": not is_auth, "done": False, "input": None,
                "note": ("AUTH-FAIL " if is_auth else "ERR ") + tail.replace("\n", " ")[:56]}
    try:
        parsed = json.loads(proc.stdout)
        events = parsed if isinstance(parsed, list) else [parsed]
        event = next(e for e in events if isinstance(e, dict) and e.get("type") == "result")
    except Exception as exc:
        return {"auth_ok": True, "done": False, "input": None, "note": f"parse: {exc}"[:60]}
    u = event.get("usage") or {}
    tot_in = sum(int(u.get(k) or 0) for k in
                 ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return {"auth_ok": not event.get("is_error"),
            "done": "OK" in (event.get("result") or ""),
            "input": tot_in, "note": ""}


def main():
    neutral = tempfile.mkdtemp(prefix="probe-cwd-")
    mincfg = tempfile.mkdtemp(prefix="probe-cfg-")  # empty; learn if auth survives
    mcp = ["--strict-mcp-config"]
    none = mcp + ["--setting-sources", ""]
    proj = mcp + ["--setting-sources", "project"]
    rungs = [
        ("0 baseline",       [],    {},                            None),
        ("1 strict-mcp",     mcp,   {},                            None),
        ("2 +no-settings",   none,  {},                            None),
        ("3 +proj-only+cwd", proj,  {},                            neutral),
        ("4 +none+cwd",      none,  {},                            neutral),
        ("5 +isolated-cfg",  none,  {"CLAUDE_CONFIG_DIR": mincfg}, neutral),
    ]
    print(f"{'rung':18} {'auth':6} {'done':6} {'input_tokens':>13}  note")
    print("-" * 74)
    for name, argv, env, cwd in rungs:
        r = _run(argv, env, cwd)
        it = f"{r['input']:,}" if isinstance(r["input"], int) else str(r["input"])
        print(f"{name:18} {str(r['auth_ok']):6} {str(r['done']):6} {it:>13}  {r['note']}")


if __name__ == "__main__":
    main()
