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
        return _build_argv(self)


# Module-level, not a method: mutmut 3.6 generates zero mutants for methods defined
# on a frozen dataclass (confirmed -- `build` above produced no `x_build__mutmut_N`
# variants under mutants/src/crucible/lean.py). Moving the actual logic to a plain
# module-level function puts it back inside the mutation-testing gate; the method
# becomes a one-line delegate with nothing left to mutate.
def _build_argv(p: LeanProfile) -> tuple[list[str], str | None]:
    argv: list[str] = []
    if p.tools is not None:
        argv += ["--tools", p.tools]
    if p.strict_mcp:
        argv.append("--strict-mcp-config")
    if p.setting_sources is not None:
        argv += ["--setting-sources", p.setting_sources]
    cwd = str(p.cwd) if p.cwd is not None else None
    return argv, cwd


AMBIENT = LeanProfile(name="ambient")
DEFAULT_LEAN = LeanProfile(tools="", setting_sources="", strict_mcp=True, name="tools-off")
