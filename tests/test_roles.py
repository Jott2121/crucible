import hashlib

from crucible import roles
from crucible.roles import RolePrompt, build_critic_prompt, build_tester_prompt


def test_tester_prompt_carries_module():
    p = build_tester_prompt("pkg/calc.py", "def f(): ...")
    assert isinstance(p, RolePrompt)
    assert "pkg/calc.py" in p.user and "def f(): ..." in p.user
    assert len(p.prompt_sha256) == 64


def test_critic_prompt_carries_survivor_diffs():
    p = build_critic_prompt("pkg/calc.py", "def f(): ...", {"m1": "--- d1 ---", "m2": "--- d2 ---"})
    assert "m1" in p.user and "--- d1 ---" in p.user and "--- d2 ---" in p.user


def test_hash_changes_when_inputs_change():
    a = build_tester_prompt("p.py", "x = 1")
    b = build_tester_prompt("p.py", "x = 2")
    assert a.prompt_sha256 != b.prompt_sha256


def test_hash_stable_for_same_inputs():
    assert (
        build_tester_prompt("p.py", "x = 1").prompt_sha256
        == build_tester_prompt("p.py", "x = 1").prompt_sha256
    )


def test_critic_hash_canonical_over_insertion_order():
    a = build_critic_prompt("p.py", "x = 1", {"m1": "d1", "m2": "d2"})
    b = build_critic_prompt("p.py", "x = 1", {"m2": "d2", "m1": "d1"})
    assert a.prompt_sha256 == b.prompt_sha256


def test_template_reads_the_crucible_package_prompts_directory(monkeypatch):
    # a real filesystem-read test can't distinguish "prompts" vs "PROMPTS" on a
    # case-insensitive filesystem (this dev machine's APFS), so intercept
    # resources.files() and assert the exact path segments requested.
    calls = []

    class FakePath:
        def __init__(self, trail):
            self.trail = trail

        def __truediv__(self, part):
            return FakePath(self.trail + (part,))

        def read_text(self):
            calls.append(self.trail)
            return "content"

    monkeypatch.setattr(roles.resources, "files", lambda pkg: FakePath((pkg,)))
    roles._template("tester.md")
    assert calls == [("crucible", "prompts", "tester.md")]


def test_build_tester_prompt_loads_the_tester_template(monkeypatch):
    captured = {}
    monkeypatch.setattr(roles, "_template", lambda name: captured.setdefault("name", name) or "SYS")
    build_tester_prompt("p.py", "x = 1")
    assert captured["name"] == "tester.md"


def test_build_critic_prompt_loads_the_critic_template(monkeypatch):
    captured = {}
    monkeypatch.setattr(roles, "_template", lambda name: captured.setdefault("name", name) or "SYS")
    build_critic_prompt("p.py", "x = 1", {})
    assert captured["name"] == "critic.md"


def test_critic_prompt_diffs_are_joined_by_a_blank_line():
    p = build_critic_prompt("p.py", "x = 1", {"m1": "d1", "m2": "d2"})
    assert "```\n\n### Mutant `m2`" in p.user


def test_finish_hashes_system_and_user_with_a_nul_separator():
    # the NUL separator is a documented part of the receipt contract: a paper reader
    # must be able to recompute prompt_sha256 from (system, user) using this exact formula.
    system, user = "SYSTEM-TEXT", "USER-TEXT"
    expected = hashlib.sha256((system + "\x00" + user).encode()).hexdigest()
    p = roles._finish(system, user)
    assert p.prompt_sha256 == expected


def test_finish_preserves_system_and_user_verbatim():
    p = roles._finish("SYSTEM-TEXT", "USER-TEXT")
    assert p.system == "SYSTEM-TEXT"
    assert p.user == "USER-TEXT"
