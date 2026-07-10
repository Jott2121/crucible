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
