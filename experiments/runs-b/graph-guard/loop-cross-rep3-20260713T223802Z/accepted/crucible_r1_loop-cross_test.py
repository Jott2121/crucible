import pytest

from graph_guard.ppr import personalized_pagerank


def _two_node_rank_after_steps(alpha, steps):
    """Independent recurrence for a -> b, with b dangling and teleport to a."""
    a_rank = 0.5
    b_rank = 0.5
    for _ in range(steps):
        next_a = (1.0 - alpha) + alpha * b_rank
        next_b = alpha * a_rank
        a_rank, b_rank = next_a, next_b
    return {"a": a_rank, "b": b_rank}


def _two_node_rank_until_tolerance(alpha, tol, max_steps):
    """Independent implementation of the documented convergence rule."""
    a_rank = 0.5
    b_rank = 0.5
    for _ in range(max_steps):
        next_a = (1.0 - alpha) + alpha * b_rank
        next_b = alpha * a_rank
        delta = abs(next_a - a_rank) + abs(next_b - b_rank)
        a_rank, b_rank = next_a, next_b
        if delta < tol:
            break
    return {"a": a_rank, "b": b_rank}


def test_duplicate_seeds_receive_duplicate_personalization_mass():
    adj = {"a": {}, "b": {}}

    result = personalized_pagerank(adj, ["a", "a", "b"], alpha=0.0)

    assert result == pytest.approx({"a": 2.0 / 3.0, "b": 1.0 / 3.0}, rel=1e-12)


def test_default_iteration_count_is_fifty_when_convergence_is_disabled():
    adj = {"a": {"b": 1.0}}
    expected = _two_node_rank_after_steps(alpha=0.9, steps=50)

    result = personalized_pagerank(adj, ["a"], alpha=0.9, tol=0.0)

    assert result == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_default_tolerance_uses_small_delta_and_stops_at_documented_convergence():
    adj = {"a": {"b": 1.0}}
    expected = _two_node_rank_until_tolerance(alpha=0.5, tol=1e-9, max_steps=50)

    result = personalized_pagerank(adj, ["a"], alpha=0.5)

    assert result == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_tolerance_equality_does_not_stop_before_the_next_iteration():
    adj = {"a": {"b": 1.0}}

    result = personalized_pagerank(adj, ["a"], alpha=0.5, tol=0.5, iters=10)

    assert result == pytest.approx({"a": 0.625, "b": 0.375}, rel=1e-12)


def test_positive_out_sum_with_a_subsequently_missing_adjacency_row_uses_empty_default():
    class VanishingLookupDict(dict):
        def __init__(self):
            super().__init__({"a": {"b": 1.0}})
            self.a_lookups = 0

        def get(self, key, default=None):
            if key == "a":
                self.a_lookups += 1
                if self.a_lookups == 1:
                    return {"b": 1.0}
                return default
            return super().get(key, default)

    adj = VanishingLookupDict()

    result = personalized_pagerank(adj, ["a"], alpha=0.5, iters=1, tol=0.0)

    assert result == pytest.approx({"a": 0.75, "b": 0.0}, rel=1e-12)
