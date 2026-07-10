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
