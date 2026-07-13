import pytest

from graph_guard.ppr import personalized_pagerank


def _swap_walk_expected(alpha, steps):
    """Independent recurrence for a -> b -> a with teleport only to a."""
    a_rank = 0.5
    b_rank = 0.5
    for _ in range(steps):
        a_rank, b_rank = alpha * b_rank + (1.0 - alpha), alpha * a_rank
    return {"a": a_rank, "b": b_rank}


def test_duplicate_seeds_receive_proportional_teleport_weight():
    adj = {"a": {}, "b": {}}

    result = personalized_pagerank(adj, ["a", "a", "b"], alpha=0.0, iters=1)

    # There are three valid seed occurrences: two for a and one for b.
    assert result["a"] == pytest.approx(2.0 / 3.0, rel=1e-12)
    assert result["b"] == pytest.approx(1.0 / 3.0, rel=1e-12)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-12)


def test_default_iteration_count_is_fifty_when_not_converged():
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    alpha = 0.99

    result = personalized_pagerank(adj, ["a"], alpha=alpha, tol=0.0)
    expected = _swap_walk_expected(alpha, 50)

    assert result["a"] == pytest.approx(expected["a"], rel=1e-12)
    assert result["b"] == pytest.approx(expected["b"], rel=1e-12)


def test_dangling_mass_includes_every_dangling_node():
    adj = {
        "a": {},
        "b": {},
        "c": {"c": 1.0},
    }

    result = personalized_pagerank(adj, ["a"], alpha=0.5, iters=1)

    # Initial rank is 1/3 each.  a and b are dangling, so their combined
    # dangling mass is 2/3.  Teleport mass is .5 + .5*(2/3) = 5/6.
    assert result["a"] == pytest.approx(5.0 / 6.0, rel=1e-12)
    assert result["b"] == pytest.approx(0.0, abs=1e-12)
    assert result["c"] == pytest.approx(1.0 / 6.0, rel=1e-12)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-12)


def test_convergence_delta_uses_difference_not_sum():
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}

    result = personalized_pagerank(adj, ["a"], alpha=0.5, tol=0.6)

    # The first update from (1/2, 1/2) is (3/4, 1/4), whose L1 delta is 1/2.
    # Since 1/2 < 0.6, the correct implementation stops after that update.
    assert result["a"] == pytest.approx(0.75, rel=1e-12)
    assert result["b"] == pytest.approx(0.25, rel=1e-12)


def test_delta_equal_to_tolerance_does_not_stop_under_strict_rule():
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}

    result = personalized_pagerank(adj, ["a"], alpha=0.5, iters=2, tol=0.5)

    # First delta is exactly 0.5, so strict "< tol" must continue to update 2.
    # Update 2 transforms (3/4, 1/4) into (5/8, 3/8).
    assert result["a"] == pytest.approx(0.625, rel=1e-12)
    assert result["b"] == pytest.approx(0.375, rel=1e-12)
