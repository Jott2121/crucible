#!/usr/bin/env python3
"""Clean tester-call measurement (Task 1 confirm). Builds the EXACT tester prompt
the crucible provider builds and calls `claude -p` via subprocess stdin -- no
shell interpolation, so a code file full of quotes/backticks/$ can't corrupt the
payload (the bug in the earlier bash harness). Compares lean flags vs baseline.
$0 metered (Max plan)."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path.home() / "ai-agentic-code-testing"
SYSTEM = (REPO / "src/crucible/prompts/tester.md").read_text()
MODULE = "rag_guard/guard.py"
SRC = (Path.home() / "rag-guard" / MODULE).read_text()
USER = f"Module: {MODULE}\n\n```python\n{SRC}\n```\n\nWrite the test file now."

LEAN = ["--tools", "", "--setting-sources", "", "--strict-mcp-config"]


def call(label, extra):
    cmd = ["claude", "-p", "--output-format", "json", "--model", "claude-sonnet-5",
           "--system-prompt", SYSTEM] + extra
    proc = subprocess.run(cmd, input=USER, capture_output=True, text=True, timeout=600)
    try:
        parsed = json.loads(proc.stdout)
        e = next(x for x in (parsed if isinstance(parsed, list) else [parsed])
                 if isinstance(x, dict) and x.get("type") == "result")
    except Exception as exc:
        print(f"  {label}: PARSE-FAIL rc={proc.returncode} {(proc.stderr or proc.stdout)[-120:]!r}")
        return
    u = e.get("usage", {})
    s = sum(int(u.get(k) or 0) for k in
            ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    print(f"  {label:10} is_error={e.get('is_error')} num_turns={e.get('num_turns')} "
          f"in={s:,} out={u.get('output_tokens')} result_chars={len(e.get('result',''))}")


if __name__ == "__main__":
    print(f"prompt built: system={len(SYSTEM)}B user={len(USER)}B (module {len(SRC)}B)")
    print("baseline receipt: tester in=325,834 / critic in=113,396")
    call("baseline", [])
    call("lean", LEAN)
