import pytest
from graph_guard.ppr import personalized_pagerank


def test_duplicate_seed_accumulates_teleport_mass():
    """Duplicate seeds should accumulate personalization mass (tele[s] += ...).

    With three isolated (dangling) nodes A, B, C and seeds=[A, A, B], the
    teleport vector should be {A: 2/3, B: 1/3}. Since every node is dangling
    (no outgoing edges), after the first iteration the rank already equals
    the teleport vector and it is a fixed point, so the final PPR result is
    exactly {A: 2/3, B: 1/3, C: 0}.

    A mutant that does `tele.get(None, 0.0)` instead of `tele.get(s, 0.0)`
    never accumulates repeated seeds, producing an un-normalized teleport
    vector ({A: 1/3, B: 1/3}, summing to 2/3 instead of 1) and thus a
    different (and non-normalized) final result.
    """
    adj = {"A": {}, "B": {}, "C": {}}
    result = personalized_pagerank(adj, ["A", "A", "B"])

    assert result["A"] == pytest.approx(2.0 / 3.0, rel=1e-6)
    assert result["B"] == pytest.approx(1.0 / 3.0, rel=1e-6)
    assert result["C"] == pytest.approx(0.0, abs=1e-9)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_default_iters_matches_explicit_50():
    """The documented default number of power-iteration steps is 50.

    Using tol=0 disables early stopping (delta is always >= 0, never < 0),
    forcing the loop to run for exactly `iters` steps. On a graph that has
    not fully converged to floating-point precision, running one extra
    iteration measurably changes the result. Therefore the default call
    (relying on the documented default iters=50) must match an explicit
    call with iters=50 exactly, for the original code. A mutant that
    changes the default to 51 will produce a different result here.
    """
    adj = {
        "A": {"B": 1.0, "C": 1.0},
        "B": {"A": 1.0},
        "C": {"A": 1.0},
    }
    result_default = personalized_pagerank(adj, [], tol=0)
    result_50 = personalized_pagerank(adj, [], iters=50, tol=0)

    assert set(result_default) == set(result_50)
    for node in result_default:
        assert result_default[node] == pytest.approx(result_50[node], rel=1e-9, abs=1e-12)


def test_default_tolerance_allows_real_convergence():
    """The documented default tolerance is 1e-9, tight enough that the power
    iteration actually runs close to the full 50 iterations (rather than
    stopping after the very first step) for a simple 2-node personalized
    PageRank problem.

    For adj = {A -> B, B -> A} (weight 1 each way) with seeds=["A"], the
    exact analytic fixed point of r = alpha * r * P + (1-alpha) * tele is:
        r_A = 1 / (1 + alpha) = 1 / 1.85 ≈ 0.540541
        r_B = alpha / (1 + alpha) = 0.85 / 1.85 ≈ 0.459459
    With alpha=0.85 and a genuinely tight tol=1e-9, the default run gets
    extremely close to this fixed point within 50 iterations (residual
    error ~1e-5).

    A mutant that inflates the default tol to ~1.000000001 causes the loop
    to break after just ONE iteration (since the very first delta of 0.15
    is already below such a huge tolerance), yielding r_A ≈ 0.575 and
    r_B ≈ 0.425 -- far outside the tolerance used below.
    """
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    result = personalized_pagerank(adj, ["A"])

    expected_a = 1.0 / 1.85
    expected_b = 0.85 / 1.85

    assert result["A"] == pytest.approx(expected_a, abs=1e-3)
    assert result["B"] == pytest.approx(expected_b, abs=1e-3)
