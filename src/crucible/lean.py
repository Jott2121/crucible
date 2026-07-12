"""Isolation intent for a claude -p subprocess, expressed as a simple interface
over hidden CLI-flag mechanics (deep-module seam). A default claude -p call is an
AGENT: it inherits the built-in tool schemas (~20k tokens) and runs multiple
internal turns, each re-reading that cached context -- ~439k across a harden.
`--tools ""` removes the tool schemas AND collapses the loop to one turn (Task 1:
119,229 -> 1,593 on the tester call, ~75x). --setting-sources ""/--strict-mcp-config
are cheap add-ons. Tokens validated by scripts/measure_tester.py; see
docs/superpowers/PROBE-RESULTS-3b.md."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LeanProfile:
    tools: str | None = None            # "" disables ALL built-in tools (primary lever)
    setting_sources: str | None = None  # "" loads no setting sources (skills, CLAUDE.md)
    strict_mcp: bool = False
    cwd: Path | None = None
    name: str = "ambient"

    def build(self) -> tuple[list[str], str | None]:
        argv: list[str] = []
        if self.tools is not None:
            argv += ["--tools", self.tools]
        if self.strict_mcp:
            argv.append("--strict-mcp-config")
        if self.setting_sources is not None:
            argv += ["--setting-sources", self.setting_sources]
        cwd = str(self.cwd) if self.cwd is not None else None
        return argv, cwd


AMBIENT = LeanProfile(name="ambient")
DEFAULT_LEAN = LeanProfile(tools="", setting_sources="", strict_mcp=True, name="tools-off")
