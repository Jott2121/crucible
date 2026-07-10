import pytest
from oracle_gate.providers import Usage

from crucible.engine import MutationOutcome
from crucible.guardrails import GuardrailViolation
from crucible.loop import LoopConfig, LoopResult, RoundReply, harden, oneshot


def outcome(survivors):
    return MutationOutcome(counts={}, survivors=list(survivors), all_mutants=10)


class FakeEnv:
    """Scripted env: measurements pop off a list; roles return canned replies."""

    def __init__(self, measurements, reject_rounds=(), fail_calls=False, reject_on_write=False):
        self.measurements = list(measurements)
        self.reject_rounds = set(reject_rounds)
        self.fail_calls = fail_calls
        self.reject_on_write = reject_on_write
        self.written, self.removed = [], []
        self._round = 0

    def measure(self):
        return self.measurements.pop(0)

    def survivor_diff(self, mid):
        return f"diff-of-{mid}"

    def _reply(self):
        if self.fail_calls:
            raise RuntimeError("model down")
        return RoundReply("```python\nassert True\n```", "a" * 64, "claude-sonnet-5", Usage(10, 5))

    def call_tester(self):
        return self._reply()

    def call_critic(self, survivor_diffs):
        self.last_diffs = survivor_diffs
        return self._reply()

    def write_test_file(self, round_no, arm, content):
        if self.reject_on_write and round_no in self.reject_rounds:
            raise GuardrailViolation("add-only violated: scripted")
        self._round = round_no
        path = f"tests/crucible_r{round_no}_{arm}_test.py"
        self.written.append(path)
        return path

    def validate(self, test_path):
        if self._round in self.reject_rounds:
            raise GuardrailViolation("invalid: scripted rejection")

    def remove_test_file(self, path):
        self.removed.append(path)

    def cost_usd(self, model, usage):
        return 0.01


def test_oneshot_is_round_zero_only():
    env = FakeEnv([outcome(["m1", "m2"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert len(result.rounds) == 1
    assert result.rounds[0].role == "tester"
    assert result.rounds[0].survivors_after == ["m1", "m2"]


def test_loop_records_kills_and_stops_clean():
    env = FakeEnv([outcome(["m1", "m2"]), outcome(["m2"]), outcome([])])
    result = harden(env, LoopConfig())
    assert result.verdict == "clean"
    assert result.rounds[1].kills == ["m1"]
    assert result.rounds[2].kills == ["m2"]


def test_loop_goes_dry_after_k_zero_kill_rounds():
    env = FakeEnv([outcome(["m1"]), outcome(["m1"]), outcome(["m1"])])
    result = harden(env, LoopConfig(dry_rounds=2))
    assert result.verdict == "dry"
    assert len(result.rounds) == 3  # tester + 2 dry critic rounds


def test_loop_hits_round_cap():
    ms = [outcome(["m1", "m2"])] + [outcome(["m1"])] * 9
    env = FakeEnv(ms)
    result = harden(env, LoopConfig(max_rounds=3, dry_rounds=99))
    assert result.verdict == "cap"
    assert len(result.rounds) == 4  # tester + 3 critic rounds


def test_rejected_round_removes_file_and_counts_dry():
    env = FakeEnv([outcome(["m1"]), outcome(["m1"])], reject_rounds={1})
    result = harden(env, LoopConfig(dry_rounds=2))
    assert result.rounds[1].status == "rejected"
    assert env.removed == ["tests/crucible_r1_loop_test.py"]
    # rejected round killed nothing; one more zero-kill round => dry
    assert result.verdict == "dry"


def test_model_failure_aborts():
    env = FakeEnv([outcome(["m1"])])
    env.fail_calls = False
    result_env = FakeEnv([outcome(["m1"])])
    result_env.fail_calls = True
    result = harden(result_env, LoopConfig())
    assert result.verdict == "aborted"
    assert result.rounds[-1].status == "aborted"


def test_total_cost_accumulates():
    env = FakeEnv([outcome(["m1"]), outcome([])])
    result = harden(env, LoopConfig())
    assert result.total_cost_usd == pytest.approx(0.02)


def test_write_rejection_is_a_rejected_round_not_a_crash():
    env = FakeEnv([outcome(["m1"]), outcome(["m1"])], reject_rounds={1}, reject_on_write=True)
    result = harden(env, LoopConfig(dry_rounds=2))
    assert result.rounds[1].status == "rejected"
    assert "add-only" in result.rounds[1].note
    assert env.removed == []  # nothing was written, nothing to remove
    assert result.verdict == "dry"


def test_oneshot_verdict_named_oneshot_when_survivors_remain():
    env = FakeEnv([outcome(["m1", "m2"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.verdict == "oneshot"


def test_abort_note_carries_exception_type():
    env = FakeEnv([outcome(["m1"])])
    env.fail_calls = True
    result = harden(env, LoopConfig())
    assert "RuntimeError" in result.rounds[-1].note


def test_rejected_tester_round_is_not_clean():
    env = FakeEnv([], reject_rounds={0})
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.verdict == "rejected"
    assert result.rounds[0].status == "rejected"
