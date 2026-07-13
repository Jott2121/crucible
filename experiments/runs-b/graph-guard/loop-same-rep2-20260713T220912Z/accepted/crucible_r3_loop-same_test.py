import pytest
from graph_guard.ppr import personalized_pagerank


def test_dangling_node_mass_redistributed_via_teleport():
    """A node with no outgoing edges ('b') must have its mass redirected back
    through the teleport (seed) distribution rather than vanishing.

    Analytic fixed point for adj={'a': {'b': 1.0}}, seeds=['a'], alpha=0.85:
        r(a) = 1 / (1 + alpha)
        r(b) = alpha / (1 + alpha)
    """
    adj = {"a": {"b": 1.0}}
    alpha = 0.85
    result = personalized_pagerank(adj, ["a"], alpha=alpha, iters=200, tol=1e-14)

    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha / (1.0 + alpha)

    assert result["a"] == pytest.approx(expected_a, rel=1e-4)
    assert result["b"] == pytest.approx(expected_b, rel=1e-4)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_single_iteration_respects_edge_weight_proportions():
    """With a single power-iteration step we can compute the exact expected
    mass distribution by hand, verifying that outgoing weight (w / out_sum)
    is used correctly for every neighbor, and that dangling nodes' mass is
    redirected through the teleport vector."""
    adj = {"a": {"b": 1.0, "c": 3.0}}
    alpha = 0.85
    result = personalized_pagerank(adj, ["a"], alpha=alpha, iters=1, tol=1e-9)

    # Manual computation of one power-iteration step from uniform start (1/3 each):
    dangling = 2.0 / 3.0  # 'b' and 'c' have no outgoing edges
    mass = (1.0 - alpha) + alpha * dangling
    expected_b = alpha * (1.0 / 3.0) * (1.0 / 4.0)
    expected_c = alpha * (1.0 / 3.0) * (3.0 / 4.0)
    expected_a = mass  # only source of 'a' mass is the teleport term

    assert result["a"] == pytest.approx(expected_a, rel=1e-9)
    assert result["b"] == pytest.approx(expected_b, rel=1e-9)
    assert result["c"] == pytest.approx(expected_c, rel=1e-9)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-9)


def test_convergence_delta_uses_difference_not_sum():
    """The convergence delta must be sum(|nxt - rank|), not sum(|nxt + rank|).
    We pick tol so that the *correct* delta triggers an early break after the
    first iteration, freezing the result before a second iteration would run.
    If delta were computed as a sum instead of a difference it would be much
    larger than tol, the loop would not break, and a second iteration would
    change the returned values."""
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    alpha = 0.85

    result = personalized_pagerank(adj, ["a"], alpha=alpha, iters=2, tol=0.2)

    # Hand computed: iteration 1 from uniform start (0.5, 0.5):
    # nxt_b = alpha*0.5*1 = 0.425
    # nxt_a = alpha*0.5*1 + (1-alpha)*1 = 0.425 + 0.15 = 0.575
    # delta = |0.575-0.5| + |0.425-0.5| = 0.15 < tol(0.2) -> break here.
    assert result["a"] == pytest.approx(0.575, rel=1e-9)
    assert result["b"] == pytest.approx(0.425, rel=1e-9)


def test_convergence_break_is_strict_inequality():
    """The break condition must be `delta < tol` (strict), not `delta <= tol`.
    We choose alpha/weights so the delta after iteration 1 exactly equals tol.
    With strict `<`, the loop must NOT break and must run a second iteration,
    changing the result. With `<=` it would break early and return the
    iteration-1 values instead."""
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    alpha = 0.5

    result = personalized_pagerank(adj, ["a"], alpha=alpha, iters=2, tol=0.5)

    # Iteration 1 from uniform start (0.5, 0.5):
    #   nxt_b = 0.5*0.5*1 = 0.25
    #   nxt_a = 0.5*0.5*1 + 0.5*1 = 0.25 + 0.5 = 0.75
    #   delta = |0.75-0.5| + |0.25-0.5| = 0.5  (== tol -> must NOT break)
    # Iteration 2 from (0.75, 0.25):
    #   nxt_b = 0.5*0.75*1 = 0.375
    #   nxt_a = 0.5*0.25*1 + 0.5*1 = 0.125 + 0.5 = 0.625
    assert result["a"] == pytest.approx(0.625, rel=1e-9)
    assert result["b"] == pytest.approx(0.375, rel=1e-9)
