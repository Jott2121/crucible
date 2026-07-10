import pytest
from oracle_gate.providers import Usage

from crucible.engine import MutationOutcome, SandboxStatsFailure
from crucible.guardrails import GuardrailViolation
from crucible.loop import LoopConfig, LoopResult, RoundReply, harden, oneshot


def outcome(survivors):
    return MutationOutcome(counts={"survived": len(survivors)}, survivors=list(survivors),
                           all_mutants=10)


class FakeEnv:
    """Scripted env: measurements pop off a list; roles return canned replies."""

    def __init__(
        self,
        measurements,
        reject_rounds=(),
        fail_calls=False,
        reject_on_write=False,
        fail_from_call=None,
        dropped_by_round=None,
    ):
        self.measurements = list(measurements)
        self.reject_rounds = set(reject_rounds)
        self.fail_calls = fail_calls
        self.dropped_by_round = dropped_by_round or {}
        # 0-indexed count of model calls (tester+critic combined, in call order);
        # once the running count reaches fail_from_call, that call and all later ones fail.
        self.fail_from_call = fail_from_call
        self.reject_on_write = reject_on_write
        self.written, self.removed = [], []
        self.calls = []  # records "tester"/"critic" in the order env was asked to speak
        self._round = 0
        self._call_count = 0

    def measure(self):
        return self.measurements.pop(0)

    def survivor_diff(self, mid):
        return f"diff-of-{mid}"

    def _reply(self, role):
        self.calls.append(role)
        should_fail = self.fail_calls or (
            self.fail_from_call is not None and self._call_count >= self.fail_from_call
        )
        self._call_count += 1
        if should_fail:
            raise RuntimeError("model down")
        return RoundReply("```python\nassert True\n```", "a" * 64, "claude-sonnet-5", Usage(10, 5))

    def call_tester(self):
        return self._reply("tester")

    def call_critic(self, survivor_diffs):
        self.last_diffs = survivor_diffs
        return self._reply("critic")

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
        return list(self.dropped_by_round.get(self._round, []))

    def remove_test_file(self, path):
        self.removed.append(path)

    def cost_usd(self, model, usage):
        return 0.01

    def assert_clean(self):
        pass


def test_tester_round_kills_are_credited_against_baseline():
    env = FakeEnv([outcome(["m1", "m2", "m3"]), outcome(["m3"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.baseline_survivors == ["m1", "m2", "m3"]
    assert result.rounds[0].kills == ["m1", "m2"]


def test_round_and_baseline_record_the_full_denominator():
    # receipts must carry the denominator: all_mutants + counts per measured round,
    # and the pristine baseline's own denominator on the result.
    env = FakeEnv([outcome(["m1", "m2"]), outcome(["m1"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.rounds[0].all_mutants == 10
    assert result.rounds[0].counts == {"survived": 1}
    assert result.baseline_all_mutants == 10
    assert result.baseline_counts == {"survived": 2}


def test_oneshot_is_round_zero_only():
    env = FakeEnv([outcome(["m1", "m2"]), outcome(["m1", "m2"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert len(result.rounds) == 1
    assert result.rounds[0].role == "tester"
    assert result.rounds[0].round == 0
    assert result.rounds[0].survivors_after == ["m1", "m2"]
    # round 0 must ask the tester, never the critic, for its reply
    assert env.calls == ["tester"]


def test_successful_round_records_the_written_test_file_path():
    # on a round that validates cleanly, rec.test_file must be the path the env
    # actually wrote to (not left at some placeholder set earlier in the try block).
    env = FakeEnv([outcome(["m1"]), outcome(["m1"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.rounds[0].test_file == "tests/crucible_r0_oneshot_test.py"
    assert result.rounds[0].test_file == env.written[0]


def test_loop_records_kills_and_stops_clean():
    # baseline, tester measure (no kills), critic kills m1, critic kills m2
    env = FakeEnv([outcome(["m1", "m2"]), outcome(["m1", "m2"]), outcome(["m2"]), outcome([])])
    result = harden(env, LoopConfig())
    assert result.verdict == "clean"
    assert result.rounds[1].kills == ["m1"]
    assert result.rounds[2].kills == ["m2"]
    # round/role/survivors_before bookkeeping on the first critic round
    assert result.rounds[1].round == 1
    assert result.rounds[1].role == "critic"
    assert result.rounds[1].survivors_before == ["m1", "m2"]
    assert env.calls == ["tester", "critic", "critic"]


def test_loop_goes_dry_after_k_zero_kill_rounds():
    env = FakeEnv([outcome(["m1"]), outcome(["m1"]), outcome(["m1"]), outcome(["m1"])])
    result = harden(env, LoopConfig(dry_rounds=2))
    assert result.verdict == "dry"
    assert len(result.rounds) == 3  # tester + 2 dry critic rounds
    assert result.total_cost_usd == pytest.approx(0.03)  # 3 rounds x $0.01 each


def test_loop_hits_round_cap():
    ms = [outcome(["m1", "m2"]), outcome(["m1", "m2"])] + [outcome(["m1"])] * 9
    env = FakeEnv(ms)
    result = harden(env, LoopConfig(max_rounds=3, dry_rounds=99))
    assert result.verdict == "cap"
    assert len(result.rounds) == 4  # tester + 3 critic rounds


def test_rejected_round_removes_file_and_counts_dry():
    # baseline, tester measure; rejected round 1 never measures; round 2 measures
    env = FakeEnv([outcome(["m1"]), outcome(["m1"]), outcome(["m1"])], reject_rounds={1})
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
    env = FakeEnv([outcome(["m1"]), outcome(["m1"]), outcome([])])
    result = harden(env, LoopConfig())
    assert result.total_cost_usd == pytest.approx(0.02)


def test_write_rejection_is_a_rejected_round_not_a_crash():
    env = FakeEnv([outcome(["m1"]), outcome(["m1"]), outcome(["m1"])],
                  reject_rounds={1}, reject_on_write=True)
    result = harden(env, LoopConfig(dry_rounds=2))
    assert result.rounds[1].status == "rejected"
    assert "add-only" in result.rounds[1].note
    assert env.removed == []  # nothing was written, nothing to remove
    assert result.verdict == "dry"


def test_oneshot_verdict_named_oneshot_when_survivors_remain():
    env = FakeEnv([outcome(["m1", "m2"]), outcome(["m1", "m2"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.verdict == "oneshot"


def test_abort_note_carries_exception_type():
    env = FakeEnv([outcome(["m1"])])
    env.fail_calls = True
    result = harden(env, LoopConfig())
    assert "RuntimeError" in result.rounds[-1].note


def test_rejected_tester_round_is_not_clean():
    env = FakeEnv([outcome(["m1"])], reject_rounds={0})
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.verdict == "rejected"
    assert result.rounds[0].status == "rejected"
    # the pre-baseline ran before the rejection, so baseline fields are still honest
    assert result.baseline_survivors == ["m1"]
    # the model was still called (and billed) before the write was rejected
    assert result.total_cost_usd == pytest.approx(0.01)


def test_critic_round_abort_uses_correct_status_and_cost():
    # tester round succeeds (round 0); the critic's model call (round 1) fails.
    env = FakeEnv([outcome(["m1"]), outcome(["m1"])], fail_from_call=1)
    result = harden(env, LoopConfig())
    assert result.verdict == "aborted"
    assert len(result.rounds) == 2
    assert result.rounds[1].role == "critic"
    assert result.rounds[1].status == "aborted"
    # the failed critic call never priced out; only the tester round's cost counts
    assert result.total_cost_usd == pytest.approx(0.01)
    # an aborted round keeps its survivor context, never reads as "0 survivors left"
    assert result.rounds[1].survivors_after == ["m1"]


def test_dry_counter_resets_to_zero_on_a_kill_round():
    # dry_rounds=1: if the dry counter didn't reset on a kill, one kill round would
    # be mistaken for a dry round and stop the loop one round too early.
    env = FakeEnv([outcome(["m1", "m2"]), outcome(["m1", "m2"]), outcome(["m2"]), outcome([])])
    result = harden(env, LoopConfig(dry_rounds=1))
    assert result.verdict == "clean"
    assert len(result.rounds) == 3  # tester + 2 critic rounds, not cut short after round 1


def test_integrity_violation_after_measure_aborts_the_run():
    # a generated test that touches the tree is tampering, not a bad round:
    # the run cannot continue (aborted), and the round keeps its survivor context.
    class TamperEnv(FakeEnv):
        def assert_clean(self):
            raise GuardrailViolation("unexpected change ' M subject_pkg/calc.py'")

    env = TamperEnv([outcome(["m1"]), outcome(["m1"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.verdict == "aborted"
    assert result.rounds[0].status == "aborted"
    assert "integrity" in result.rounds[0].note
    assert result.rounds[0].survivors_after == ["m1"]


def test_post_write_sandbox_stats_failure_is_a_rejected_round_not_a_plausible_zero():
    # v5: a generated test that passes validity but crashes mutmut's own
    # sandbox (SandboxStatsFailure from the post-write env.measure() call)
    # must reject the round -- never get recorded as a real zero-kill
    # measurement, which is exactly the silent-corruption bug this fixes.
    class SandboxFailEnv(FakeEnv):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._measure_calls = 0

        def measure(self):
            self._measure_calls += 1
            if self._measure_calls == 2:  # the post-write measure, not the baseline
                raise SandboxStatsFailure("mutmut run failed: runner returned 1")
            return super().measure()

    env = SandboxFailEnv([outcome(["m1", "m2"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.rounds[0].status == "rejected"
    assert "sandbox-invalid" in result.rounds[0].note
    assert "runner returned 1" in result.rounds[0].note
    assert result.rounds[0].test_file is None
    assert result.rounds[0].survivors_after == ["m1", "m2"]
    assert env.removed == ["tests/crucible_r0_oneshot_test.py"]
    assert result.verdict == "rejected"


def test_baseline_sandbox_stats_failure_propagates_uncaught():
    # v5: the PRE-round baseline measure can't be broken by a generated test
    # (none exists yet) -- if it raises SandboxStatsFailure, that is a real
    # subject config error and must crash loud, not be swallowed as a round.
    class BrokenBaselineEnv(FakeEnv):
        def measure(self):
            raise SandboxStatsFailure("subject config is broken")

    env = BrokenBaselineEnv([])
    with pytest.raises(SandboxStatsFailure, match="subject config is broken"):
        oneshot(env, LoopConfig(arm="oneshot"))


def test_on_round_streams_each_record_in_order():
    # the caller's on_round hook must see every record, in order, as it lands —
    # that is what makes receipts durable per round instead of buffered to the end.
    env = FakeEnv([outcome(["m1", "m2"]), outcome(["m1", "m2"]), outcome(["m2"]), outcome([])])
    seen = []
    result = harden(env, LoopConfig(), on_round=seen.append)
    assert seen == result.rounds
    assert len(seen) == 3


def test_round_records_dropped_tests_from_env_validate():
    # v3 salvage: env.validate returns the names of any pristine-failing tests it
    # dropped from the file; the round must carry that forward in its receipt rather
    # than discarding it, and a round where nothing was dropped keeps an empty list.
    env = FakeEnv(
        [outcome(["m1", "m2"]), outcome(["m1"])],
        dropped_by_round={0: ["test_wrong_oracle"]},
    )
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.rounds[0].dropped_tests == ["test_wrong_oracle"]
    assert result.rounds[0].status == "ok"  # a salvaged round is still ok, not rejected


def test_round_dropped_tests_defaults_to_empty_list_when_nothing_dropped():
    env = FakeEnv([outcome(["m1"]), outcome(["m1"])])
    result = oneshot(env, LoopConfig(arm="oneshot"))
    assert result.rounds[0].dropped_tests == []


def test_clean_verdict_when_last_round_exhausts_the_budget():
    # the final round exactly kills the last survivor at the budget cap: the loop's
    # top-of-iteration early-return never fires, so the tail "clean" computation must.
    env = FakeEnv([outcome(["m1"]), outcome(["m1"]), outcome([])])
    result = harden(env, LoopConfig(max_rounds=1, dry_rounds=99))
    assert result.verdict == "clean"
    assert len(result.rounds) == 2
