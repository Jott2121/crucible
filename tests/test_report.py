import pytest

from crucible.report import _killed, mcnemar_exact, paired_kills, summarize


def run_dict(survivors_baseline, kills_by_round, cost=1.0, arm="loop", round0_kills=None):
    """Baseline = round 0's survivors_before (the pristine pre-measure); round 0
    may itself kill (the tester's honest credit)."""
    round0_kills = round0_kills or []
    after0 = [m for m in survivors_baseline if m not in round0_kills]
    rounds = [{"round": 0, "role": "tester", "kills": round0_kills,
               "survivors_before": survivors_baseline, "survivors_after": after0,
               "cost_usd": 0.5, "status": "ok"}]
    for i, kills in enumerate(kills_by_round, start=1):
        rounds.append({"round": i, "role": "critic", "kills": kills,
                       "survivors_after": [], "cost_usd": 0.5, "status": "ok"})
    return {"meta": {"arm": arm}, "rounds": rounds,
            "result": {"verdict": "dry", "total_cost_usd": cost}}


def test_mcnemar_exact_known_values():
    # b=8, c=2 -> two-sided exact p ~ 0.109375
    assert mcnemar_exact(8, 2) == pytest.approx(0.109375)
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(10, 0) == pytest.approx(2 * (0.5 ** 10), rel=1e-9)


def test_mcnemar_exact_p_value_is_capped_at_one():
    # b=c=1 drives the uncapped formula to 2*0.75 = 1.5; a p-value must never exceed 1.0
    assert mcnemar_exact(1, 1) == 1.0


def test_paired_kills_2x2():
    # honest semantics: same pristine baseline both runs; kills split across
    # round 0 (tester credit) and later rounds — the 2x2 shape is unchanged.
    a = run_dict(["m1", "m2", "m3", "m4"], [["m2"]], round0_kills=["m1"])
    b = run_dict(["m1", "m2", "m3", "m4"], [["m3"]], round0_kills=["m2"])
    both, a_only, b_only, neither = paired_kills(a, b)
    assert (both, a_only, b_only, neither) == (1, 1, 1, 1)


def test_paired_kills_uses_union_of_baselines_not_intersection():
    a = run_dict(["m1", "m2"], [["m1"]])  # baseline {m1,m2}, kills m1
    b = run_dict(["m2", "m3"], [["m3"]])  # baseline {m2,m3}, kills m3
    both, a_only, b_only, neither = paired_kills(a, b)
    # union of baselines = {m1,m2,m3}; ka={m1}; kb={m3}
    assert (both, a_only, b_only, neither) == (0, 1, 1, 1)


def test_killed_handles_rounds_missing_kills_key():
    # a round dict with no "kills" key at all (e.g. hand-built or an older receipt
    # schema) must be treated as "killed nothing that round", not crash.
    run = {"rounds": [{"round": 0, "survivors_after": ["m1"]}]}
    assert _killed(run) == set()


def test_summarize_full_shape_and_values():
    run = run_dict(["m1", "m2", "m3"], [["m1", "m2"]], cost=6.0, arm="critic-arm")
    s = summarize(run)
    assert s == {
        "arm": "critic-arm",
        "verdict": "dry",
        "baseline_survivors": 3,
        "killed": 2,
        "cost_usd": pytest.approx(6.0),
        "cost_per_kill": pytest.approx(3.0),
    }


def test_summarize_incomplete_run_has_default_cost_and_verdict():
    run = {"meta": {"arm": "x"}, "rounds": [{"round": 0, "kills": [], "survivors_after": ["m1"]}],
           "result": None}
    s = summarize(run)
    assert s["cost_usd"] == pytest.approx(0.0)
    assert s["verdict"] == "incomplete"


def test_summarize_zero_kills_has_no_cost_per_kill():
    assert summarize(run_dict(["m1"], [[]]))["cost_per_kill"] is None
