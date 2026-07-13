import pytest

from graph_guard.ppr import personalized_pagerank


def test_ppr_dangling_node_closed_form():
    """Two-node graph with a dangling node 'a' (no outgoing edges) and 'b' -> 'a'.
    Seed on 'b'. Closed-form fixed point (derived independently):
        rank_b = 1 / (1 + alpha)
        rank_a = alpha * rank_b
    This exercises the dangling-mass accounting (out_sum lookup) and the
    adjacency lookup inside the main PPR update loop.
    """
    adj = {"a": {}, "b": {"a": 1.0}}
    alpha = 0.85

    result = personalized_pagerank(adj, ["b"], alpha=alpha, iters=200, tol=1e-14)

    expected_b = 1.0 / (1.0 + alpha)
    expected_a = alpha * expected_b

    assert result["b"] == pytest.approx(expected_b, rel=1e-6)
    assert result["a"] == pytest.approx(expected_a, rel=1e-6)
    # sanity: scores sum to ~1
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_break_requires_strictly_less_than_tol():
    """The convergence check must be `delta < tol` (strict), not `delta <= tol`.

    We build a 3-cycle graph and seed on 'a'. We first compute the rank after
    exactly one iteration (iters=1 always performs exactly one update,
    regardless of tol). We then compute the delta between that result and the
    uniform initial rank. Using that *exact* delta as `tol` for a 2-iteration
    run must NOT trigger an early stop after iteration 1 (since
    delta < delta is False) — so the algorithm must still run the second
    iteration and match a reference run with tol=0.0 for 2 iterations.

    A mutant using `delta <= tol` would stop after iteration 1 instead,
    producing the (different) 1-iteration result.
    """
    adj = {"a": {"b": 1.0}, "b": {"c": 1.0}, "c": {"a": 1.0}}
    seeds = ["a"]
    alpha = 0.85
    nodes = ["a", "b", "c"]
    n = len(nodes)
    rank0 = {v: 1.0 / n for v in nodes}

    # Exactly one iteration (iters bound alone stops the loop here).
    rank1 = personalized_pagerank(adj, seeds, alpha=alpha, iters=1, tol=0.0)

    delta1 = sum(abs(rank1[v] - rank0[v]) for v in nodes)
    assert delta1 > 0  # not yet converged after 1 iteration

    # Reference for 2 iterations, with a tol that can never trigger an early stop.
    rank2_ref = personalized_pagerank(adj, seeds, alpha=alpha, iters=2, tol=0.0)

    # Sanity: the process genuinely changes between iteration 1 and 2.
    assert any(abs(rank1[v] - rank2_ref[v]) > 1e-9 for v in nodes)

    # With tol set exactly to delta1, original (`<`) must NOT break early.
    result = personalized_pagerank(adj, seeds, alpha=alpha, iters=2, tol=delta1)

    for v in nodes:
        assert result[v] == pytest.approx(rank2_ref[v], rel=1e-9, abs=1e-12)
