from pathlib import Path

from oracle_gate.providers import Usage

from crucible.env import SubjectEnv
from crucible.providers_ext import FakeProvider

GOOD_TESTS = """```python
from subject_pkg.calc import acceptance_rate, clamp

def test_clamp_low():
    assert clamp(-5, 0, 10) == 0

def test_rate_value():
    assert acceptance_rate(10, 5) == 0.5
```"""


def _env(tmp_path, replies):
    import shutil, subprocess
    from pathlib import Path

    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    subprocess.run(["git", "init", "-q"], cwd=subject, check=True)
    subprocess.run(["git", "add", "-A"], cwd=subject, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=subject, check=True,
    )
    p = FakeProvider(replies)
    return SubjectEnv(
        subject_dir=subject, tester_provider=p, tester_model="fake-model",
        critic_provider=p, critic_model="fake-model", module_path="subject_pkg/calc.py",
    )


def test_call_tester_returns_reply_with_hash(tmp_path):
    env = _env(tmp_path, [GOOD_TESTS])
    reply = env.call_tester()
    assert "clamp_low" in reply.text and len(reply.prompt_sha256) == 64


def test_write_and_remove_test_file_respects_add_only(tmp_path):
    env = _env(tmp_path, [])
    path = env.write_test_file(1, "loop", "def test_x():\n    assert True\n")
    assert (env.subject_dir / path).exists()
    env.remove_test_file(path)
    assert not (env.subject_dir / path).exists()


def test_engine_artifacts_do_not_trip_add_only(tmp_path):
    env = _env(tmp_path, [])
    (env.subject_dir / "mutants").mkdir()
    (env.subject_dir / "mutants" / "junk.json").write_text("{}")
    (env.subject_dir / "coverage.json").write_text("{}")
    path = env.write_test_file(1, "loop", "def test_x():\n    assert True\n")
    assert (env.subject_dir / path).exists()


def test_preflight_raises_on_non_git_dir(tmp_path):
    import pytest

    plain = tmp_path / "plain"
    plain.mkdir()
    env = SubjectEnv(subject_dir=plain, tester_provider=None, tester_model="m",
                     critic_provider=None, critic_model="m", module_path="x.py")
    with pytest.raises(RuntimeError):
        env.preflight()


def test_preflight_raises_on_dirty_clone(tmp_path):
    import pytest

    env = _env(tmp_path, [])
    (env.subject_dir / "stray.txt").write_text("uncommitted")
    with pytest.raises(RuntimeError, match="dirty"):
        env.preflight()


def test_preflight_raises_on_red_pristine_suite(tmp_path):
    import pytest, subprocess

    env = _env(tmp_path, [])
    (env.subject_dir / "tests" / "test_red.py").write_text(
        "def test_always_fails():\n    assert False\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=env.subject_dir, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "red"],
        cwd=env.subject_dir, check=True,
    )
    with pytest.raises(RuntimeError, match="red on pristine"):
        env.preflight()


def test_preflight_green_returns_head_sha(tmp_path):
    env = _env(tmp_path, [])
    sha = env.preflight()
    assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha)


def test_preflight_writes_scope_and_commits_it_in_the_clone(tmp_path):
    env = _env(tmp_path, [])
    seed = env.head_sha()
    sha = env.preflight(module_path="subject_pkg/calc.py")
    text = (env.subject_dir / "pyproject.toml").read_text()
    assert "[tool.mutmut]" in text and '"subject_pkg/calc.py"' in text
    # the scope edit is committed inside the clone, so the tree ends clean and
    # the returned sha (which receipts bind to) INCLUDES the scope
    assert env._filtered_status().strip() == ""
    assert sha != seed and len(sha) == 40


def test_preflight_writes_also_copy_when_scope_given(tmp_path):
    import shutil, subprocess
    from pathlib import Path

    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    subprocess.run(["git", "init", "-q"], cwd=subject, check=True)
    subprocess.run(["git", "add", "-A"], cwd=subject, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=subject, check=True,
    )
    p = FakeProvider([])
    env = SubjectEnv(
        subject_dir=subject, tester_provider=p, tester_model="fake-model",
        critic_provider=p, critic_model="fake-model", module_path="subject_pkg/calc.py",
        scope={"also_copy": ["subject_pkg"], "pytest_args": ["tests/test_calc.py"]},
    )
    env.preflight(module_path="subject_pkg/calc.py")
    text = (env.subject_dir / "pyproject.toml").read_text()
    assert 'also_copy = ["subject_pkg"]' in text
    assert 'pytest_add_cli_args_test_selection = ["tests/test_calc.py"]' in text


def test_preflight_writes_extra_files_and_commits_them_with_the_scope(tmp_path):
    # v7: import shims (e.g. a src-layout conftest.py) are written into the
    # clone root and committed in the SAME commit as the [tool.mutmut] scope
    # write, so a receipt's head_sha covers the shim too.
    import shutil, subprocess
    from pathlib import Path

    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    subprocess.run(["git", "init", "-q"], cwd=subject, check=True)
    subprocess.run(["git", "add", "-A"], cwd=subject, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=subject, check=True,
    )
    conftest_body = "import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent / \"src\"))\n"
    p = FakeProvider([])
    env = SubjectEnv(
        subject_dir=subject, tester_provider=p, tester_model="fake-model",
        critic_provider=p, critic_model="fake-model", module_path="subject_pkg/calc.py",
        scope={"extra_files": {"conftest.py": conftest_body}},
    )
    env.preflight(module_path="subject_pkg/calc.py")

    conftest = env.subject_dir / "conftest.py"
    assert conftest.read_text() == conftest_body
    # committed, not just written -- the tree must end clean
    assert env._filtered_status().strip() == ""
    committed = subprocess.run(
        ["git", "show", "HEAD:conftest.py"], cwd=subject, capture_output=True, text=True, check=True
    ).stdout
    assert committed == conftest_body
    # pyproject.toml (the scope write) is in the SAME commit as conftest.py
    changed_files = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=subject, capture_output=True, text=True, check=True,
    ).stdout.split()
    assert set(changed_files) == {"pyproject.toml", "conftest.py"}
    subject_line = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=subject, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert subject_line == "crucible: scope mutmut to subject_pkg/calc.py (+shims)"


def test_preflight_commit_message_has_no_shims_suffix_without_extra_files(tmp_path):
    env = _env(tmp_path, [])
    env.preflight(module_path="subject_pkg/calc.py")
    subject_line = subprocess_log_subject(env.subject_dir)
    assert subject_line == "crucible: scope mutmut to subject_pkg/calc.py"


def subprocess_log_subject(cwd):
    import subprocess

    return subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_preflight_skips_rewriting_extra_file_when_content_is_unchanged(tmp_path):
    # a second preflight call against an already-scoped, already-shimmed clone
    # (the real cell-isolation flow: reset_clone + preflight per cell) must be
    # a true no-op -- no new commit, since neither the scope nor the shim body
    # actually changed.
    import shutil, subprocess
    from pathlib import Path

    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    subprocess.run(["git", "init", "-q"], cwd=subject, check=True)
    subprocess.run(["git", "add", "-A"], cwd=subject, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=subject, check=True,
    )
    conftest_body = "import sys\n"
    p = FakeProvider([])
    env = SubjectEnv(
        subject_dir=subject, tester_provider=p, tester_model="fake-model",
        critic_provider=p, critic_model="fake-model", module_path="subject_pkg/calc.py",
        scope={"extra_files": {"conftest.py": conftest_body}},
    )
    first_sha = env.preflight(module_path="subject_pkg/calc.py")
    env.reset_clone()
    second_sha = env.preflight(module_path="subject_pkg/calc.py")
    assert first_sha == second_sha  # nothing new to commit
    assert (env.subject_dir / "conftest.py").read_text() == conftest_body


def test_call_tester_threads_import_hint_from_scope(tmp_path, monkeypatch):
    from crucible import env as env_module
    from crucible.roles import RolePrompt

    captured = {}

    def fake_build_tester_prompt(module_path, module_source, import_hint=None):
        captured["import_hint"] = import_hint
        return RolePrompt(system="S", user="U", prompt_sha256="a" * 64)

    monkeypatch.setattr(env_module, "build_tester_prompt", fake_build_tester_prompt)

    env = _env(tmp_path, ["reply"])
    env.scope = {"import_hint": "Import as `import calc`."}
    env.call_tester()
    assert captured["import_hint"] == "Import as `import calc`."


def test_call_tester_passes_none_hint_when_scope_has_none(tmp_path, monkeypatch):
    from crucible import env as env_module
    from crucible.roles import RolePrompt

    captured = {}

    def fake_build_tester_prompt(module_path, module_source, import_hint=None):
        captured["import_hint"] = import_hint
        return RolePrompt(system="S", user="U", prompt_sha256="a" * 64)

    monkeypatch.setattr(env_module, "build_tester_prompt", fake_build_tester_prompt)

    env = _env(tmp_path, ["reply"])  # no scope at all
    env.call_tester()
    assert captured["import_hint"] is None


def test_call_critic_threads_import_hint_from_scope(tmp_path, monkeypatch):
    from crucible import env as env_module
    from crucible.roles import RolePrompt

    captured = {}

    def fake_build_critic_prompt(module_path, module_source, survivor_diffs, import_hint=None):
        captured["import_hint"] = import_hint
        return RolePrompt(system="S", user="U", prompt_sha256="a" * 64)

    monkeypatch.setattr(env_module, "build_critic_prompt", fake_build_critic_prompt)

    env = _env(tmp_path, ["reply"])
    env.scope = {"import_hint": "Import as `import calc`."}
    env.call_critic({})
    assert captured["import_hint"] == "Import as `import calc`."


def test_assert_clean_tolerates_engine_artifacts_and_generated_tests_only(tmp_path):
    import pytest

    from crucible.guardrails import GuardrailViolation

    env = _env(tmp_path, [])
    # engine artifacts + a crucible-generated test file: fine
    (env.subject_dir / "mutants").mkdir()
    (env.subject_dir / "coverage.json").write_text("{}")
    (env.subject_dir / "tests" / "crucible_r0_loop_test.py").write_text("def test_x():\n    assert True\n")
    env.assert_clean()
    # a MODIFIED tracked file is tampering — any non-?? line is a violation
    (env.subject_dir / "subject_pkg" / "calc.py").write_text("# tampered\n")
    with pytest.raises(GuardrailViolation):
        env.assert_clean()


def test_preflight_accepts_subject_with_no_tests(tmp_path):
    # third-party subjects get their tests stripped; "no tests collected"
    # (pytest exit 5) is a valid pristine state — crucible's job is to create tests
    import shutil, subprocess
    from pathlib import Path

    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    shutil.rmtree(subject / "tests")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    env = SubjectEnv(subject_dir=subject, tester_provider=FakeProvider([]),
                     tester_model="fake-model", critic_provider=FakeProvider([]),
                     critic_model="fake-model", module_path="subject_pkg/calc.py")
    sha = env.preflight("subject_pkg/calc.py")
    assert len(sha) == 40


def test_preflight_creates_pyproject_when_subject_clone_has_none(tmp_path):
    # a clone with no pyproject.toml/setup.py/setup.cfg at all (e.g.
    # attrition-risk-ml) has nowhere for mutmut to read [tool.mutmut] from;
    # preflight must create a minimal scope-only file rather than raising
    # ScopeError, since crucible operates on a disposable clone
    import shutil, subprocess
    from pathlib import Path

    subject = tmp_path / "subject"
    shutil.copytree(Path(__file__).parent / "fixtures" / "subject", subject)
    (subject / "pyproject.toml").unlink()
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=subject, check=True)
    env = SubjectEnv(subject_dir=subject, tester_provider=FakeProvider([]),
                     tester_model="fake-model", critic_provider=FakeProvider([]),
                     critic_model="fake-model", module_path="subject_pkg/calc.py")
    sha = env.preflight("subject_pkg/calc.py")
    assert len(sha) == 40
    text = (subject / "pyproject.toml").read_text()
    assert "[tool.mutmut]" in text and '"subject_pkg/calc.py"' in text


SALVAGEABLE_TESTS = (
    "from subject_pkg.calc import acceptance_rate, clamp\n\n\n"
    "def test_clamp_low():\n    assert clamp(-5, 0, 10) == 0\n\n\n"
    "def test_rate_value():\n    assert acceptance_rate(10, 5) == 0.5\n\n\n"
    "def test_wrong_oracle():\n    assert acceptance_rate(10, 5) == 0.99\n"
)

ALL_GOOD_TESTS = (
    "from subject_pkg.calc import acceptance_rate, clamp\n\n\n"
    "def test_clamp_low():\n    assert clamp(-5, 0, 10) == 0\n\n\n"
    "def test_rate_value():\n    assert acceptance_rate(10, 5) == 0.5\n"
)

ALL_WRONG_TESTS = (
    "from subject_pkg.calc import acceptance_rate\n\n\n"
    "def test_wrong_a():\n    assert acceptance_rate(10, 5) == 0.99\n\n\n"
    "def test_wrong_b():\n    assert acceptance_rate(1, 1) == 0.5\n"
)


def test_validate_salvages_the_pristine_failing_test_and_returns_its_name(tmp_path):
    env = _env(tmp_path, [])
    path = env.write_test_file(0, "loop", SALVAGEABLE_TESTS)
    dropped = env.validate(path)
    assert dropped == ["test_wrong_oracle"]
    remaining = (env.subject_dir / path).read_text()
    assert "test_wrong_oracle" not in remaining
    assert "test_clamp_low" in remaining and "test_rate_value" in remaining


def test_validate_all_green_returns_empty_list_and_leaves_file_untouched(tmp_path):
    env = _env(tmp_path, [])
    path = env.write_test_file(0, "loop", ALL_GOOD_TESTS)
    dropped = env.validate(path)
    assert dropped == []
    assert (env.subject_dir / path).read_text() == ALL_GOOD_TESTS + "\n"


def test_validate_raises_when_every_test_has_a_wrong_oracle(tmp_path):
    import pytest

    from crucible.guardrails import GuardrailViolation

    env = _env(tmp_path, [])
    path = env.write_test_file(0, "loop", ALL_WRONG_TESTS)
    with pytest.raises(GuardrailViolation, match="invalid"):
        env.validate(path)


def test_remove_test_file_unlinks_when_no_artifact_dir_set(tmp_path):
    env = _env(tmp_path, [])
    path = env.write_test_file(1, "loop", "def test_x():\n    assert True\n")
    env.remove_test_file(path)
    assert not (env.subject_dir / path).exists()


def test_set_artifact_dir_preserves_rejected_file_instead_of_deleting(tmp_path):
    env = _env(tmp_path, [])
    artifact_dir = tmp_path / "run-dir"
    artifact_dir.mkdir()
    env.set_artifact_dir(artifact_dir)
    path = env.write_test_file(1, "loop", "def test_x():\n    assert True\n")
    env.remove_test_file(path)
    assert not (env.subject_dir / path).exists()
    preserved = artifact_dir / "rejected" / "rejected-crucible_r1_loop_test.py"
    assert preserved.exists()
    assert preserved.read_text() == "def test_x():\n    assert True\n\n"


def test_validate_preserves_pre_salvage_original_when_artifact_dir_set(tmp_path):
    env = _env(tmp_path, [])
    artifact_dir = tmp_path / "run-dir"
    artifact_dir.mkdir()
    env.set_artifact_dir(artifact_dir)
    path = env.write_test_file(0, "loop", SALVAGEABLE_TESTS)
    dropped = env.validate(path)
    assert dropped == ["test_wrong_oracle"]
    orig = artifact_dir / "salvaged" / f"{Path(path).name}.orig"
    assert orig.exists()
    assert "test_wrong_oracle" in orig.read_text()
    assert "test_wrong_oracle" not in (env.subject_dir / path).read_text()


def test_validate_writes_no_salvaged_copy_when_nothing_was_dropped(tmp_path):
    env = _env(tmp_path, [])
    artifact_dir = tmp_path / "run-dir"
    artifact_dir.mkdir()
    env.set_artifact_dir(artifact_dir)
    path = env.write_test_file(0, "loop", ALL_GOOD_TESTS)
    dropped = env.validate(path)
    assert dropped == []
    assert not (artifact_dir / "salvaged").exists()


def test_write_test_file_succeeds_when_clone_has_no_tests_dir(tmp_path):
    # a stripped subject (tests/ removed by git rm) has no tests dir at all;
    # write_test_file must create it rather than crash FileNotFoundError
    import shutil

    env = _env(tmp_path, [])
    shutil.rmtree(env.subject_dir / "tests")
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=env.subject_dir, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "strip tests"],
        cwd=env.subject_dir, check=True,
    )
    path = env.write_test_file(1, "loop", "def test_x():\n    assert True\n")
    assert (env.subject_dir / path).exists()


def test_write_test_file_add_only_accepts_file_in_previously_nonexistent_tests_dir(tmp_path):
    # regression: git status --porcelain (default -unormal) collapses a wholly
    # new untracked dir to `?? tests/`, which the add-only allowlist (file
    # paths) rejects as unexpected -- -uall must enumerate the file itself
    import shutil, subprocess

    env = _env(tmp_path, [])
    shutil.rmtree(env.subject_dir / "tests")
    subprocess.run(["git", "add", "-A"], cwd=env.subject_dir, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "strip tests"],
        cwd=env.subject_dir, check=True,
    )
    # write_test_file itself calls assert_add_only internally; if the dir-collapse
    # bug were present this would raise GuardrailViolation instead of returning
    path = env.write_test_file(1, "loop", "def test_x():\n    assert True\n")
    assert (env.subject_dir / path).exists()
    # and the post-round integrity check (assert_clean) must also pass clean
    env.assert_clean()


def test_reset_clone_removes_stray_artifacts_and_reverts_tracked_files(tmp_path):
    env = _env(tmp_path, [])
    # a prior cell's accepted generated test, left untracked in the clone
    (env.subject_dir / "tests" / "crucible_r9_x_test.py").write_text(
        "def test_stray():\n    assert True\n"
    )
    # engine cache from a prior cell's mutation run
    (env.subject_dir / "mutants").mkdir()
    (env.subject_dir / "mutants" / "junk.json").write_text("{}")
    # a tracked file modified in place (e.g. preflight's scope-write, uncommitted)
    calc_path = env.subject_dir / "subject_pkg" / "calc.py"
    original = calc_path.read_text()
    calc_path.write_text(original + "\n# tampered\n")

    env.reset_clone()

    assert not (env.subject_dir / "tests" / "crucible_r9_x_test.py").exists()
    assert not (env.subject_dir / "mutants").exists()
    assert calc_path.read_text() == original
    assert env._filtered_status().strip() == ""


def test_retry_then_raise(tmp_path):
    class DyingProvider(FakeProvider):
        def __init__(self):
            super().__init__([])
            self.calls = 0

        def complete_with_usage(self, system, user, model=None):
            self.calls += 1
            raise RuntimeError("boom")

    env = _env(tmp_path, [])
    env.tester_provider = dying = DyingProvider()
    env._sleep = lambda s: None  # no real backoff in tests
    try:
        env.call_tester()
        assert False, "should raise"
    except RuntimeError:
        pass
    assert dying.calls == 3
