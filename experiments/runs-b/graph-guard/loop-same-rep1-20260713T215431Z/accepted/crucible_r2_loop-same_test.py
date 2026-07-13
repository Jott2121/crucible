import pytest
from graph_guard.ppr import personalized_pagerank


def test_duplicate_seeds_normalize_same_as_single_seed():
    """Duplicate seed ids should not change the outcome: normalized teleport
    mass for a seed must be the accumulated sum over its occurrences divided
    by the seed-list length, which always nets to the same distribution as a
    single occurrence of that seed."""
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}

    result_single = personalized_pagerank(adj, ["A"])
    result_dup = personalized_pagerank(adj, ["A", "A"])

    assert result_single.keys() == result_dup.keys()
    for node in result_single:
        assert result_dup[node] == pytest.approx(result_single[node], rel=1e-6)


def test_default_iters_and_tol_match_documented_defaults():
    """The documented defaults are iters=50, tol=1e-9. Calling with those
    explicit values must reproduce exactly what happens when the caller
    relies on the defaults, for a graph that has not yet converged to
    tol=1e-9 by iteration 50 (so any change to either default measurably
    changes the result)."""
    adj = {
        "A": {"B": 1.0},
        "B": {"C": 1.0},
        "C": {"A": 1.0},
    }
    seeds = ["A"]

    result_default = personalized_pagerank(adj, seeds)
    result_explicit = personalized_pagerank(adj, seeds, iters=50, tol=1e-9)

    assert result_default.keys() == result_explicit.keys()
    for node in result_default:
        assert result_default[node] == pytest.approx(result_explicit[node], rel=1e-6)


def test_convergence_delta_uses_subtraction_not_addition():
    """On a 2-node symmetric cycle with a single seed, starting from the
    uniform distribution, the first-iteration update is exactly:
        nxt = {A: 0.575, B: 0.425}
    (alpha=0.85 default), giving delta = |0.575-0.5| + |0.425-0.5| = 0.15.
    With tol=1.0, the algorithm must stop right after this first update
    (0.15 < 1.0), so the returned ranks must be exactly this first-iteration
    result even though iters=5 would allow further refinement."""
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    seeds = ["A"]

    result = personalized_pagerank(adj, seeds, alpha=0.85, iters=5, tol=1.0)

    assert result["A"] == pytest.approx(0.575, rel=1e-6)
    assert result["B"] == pytest.approx(0.425, rel=1e-6)
