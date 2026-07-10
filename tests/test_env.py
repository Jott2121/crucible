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
