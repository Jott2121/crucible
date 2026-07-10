"""Assemble Tester/Critic prompts from versioned template files and hash what was sent.

The hash goes into every receipt: a reader of the paper can verify exactly which prompt
produced which tests, and any prompt edit changes the hash trail.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class RolePrompt:
    system: str
    user: str
    prompt_sha256: str


def _template(name: str) -> str:
    return (resources.files("crucible") / "prompts" / name).read_text()


def _finish(system: str, user: str) -> RolePrompt:
    digest = hashlib.sha256((system + "\x00" + user).encode()).hexdigest()
    return RolePrompt(system=system, user=user, prompt_sha256=digest)


def _import_hint_line(import_hint: str | None) -> str:
    # v7: the hint is per-subject input (varies with which module is under
    # test), so it belongs in the hashed user text, not the shared system
    # template -- hash discipline means a prompt-sha256 must change whenever
    # the actual instructions sent for THIS call change.
    return f"One more mandatory rule: {import_hint}\n\n" if import_hint else ""


def build_tester_prompt(module_path: str, module_source: str,
                        import_hint: str | None = None) -> RolePrompt:
    system = _template("tester.md")
    user = (
        f"Module `{module_path}`:\n\n```python\n{module_source}\n```\n\n"
        f"{_import_hint_line(import_hint)}Write the test file now."
    )
    return _finish(system, user)


def build_critic_prompt(module_path, module_source, survivor_diffs,
                        import_hint: str | None = None) -> RolePrompt:
    system = _template("critic.md")
    diffs = "\n\n".join(
        f"### Mutant `{mid}`\n```diff\n{d}\n```" for mid, d in sorted(survivor_diffs.items())
    )
    user = (
        f"Module `{module_path}`:\n\n```python\n{module_source}\n```\n\n"
        f"## Surviving mutants ({len(survivor_diffs)})\n\n{diffs}\n\n"
        f"{_import_hint_line(import_hint)}Write the test file now."
    )
    return _finish(system, user)
