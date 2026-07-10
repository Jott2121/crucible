import pytest

from crucible.report import mcnemar_exact, paired_kills, summarize


def run_dict(survivors_baseline, kills_by_round, cost=1.0, arm="loop"):
    rounds = [{"round": 0, "role": "tester", "kills": [], "survivors_after": survivors_baseline,
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


def test_paired_kills_2x2():
    a = run_dict(["m1", "m2", "m3", "m4"], [["m1", "m2"]])
    b = run_dict(["m1", "m2", "m3", "m4"], [["m2", "m3"]])
    both, a_only, b_only, neither = paired_kills(a, b)
    assert (both, a_only, b_only, neither) == (1, 1, 1, 1)


def test_summarize():
    s = summarize(run_dict(["m1", "m2"], [["m1"]], cost=2.0))
    assert s["baseline_survivors"] == 2 and s["killed"] == 1
    assert s["cost_per_kill"] == pytest.approx(2.0)


def test_summarize_zero_kills_has_no_cost_per_kill():
    assert summarize(run_dict(["m1"], [[]]))["cost_per_kill"] is None
