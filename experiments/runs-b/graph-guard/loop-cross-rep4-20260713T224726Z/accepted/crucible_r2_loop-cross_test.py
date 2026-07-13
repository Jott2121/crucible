import pytest

from graph_guard.ppr import personalized_pagerank


def test_default_iteration_count_and_tolerance_produce_fifty_cycle_updates():
    adjacency = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    alpha = 0.85

    scores = personalized_pagerank(adjacency, ["a"], alpha=alpha)

    stationary_a = 1.0 / (1.0 + alpha)
    expected_a = stationary_a + (0.5 - stationary_a) * (-alpha) ** 50

    assert scores["a"] == pytest.approx(expected_a, rel=1e-6)
    assert scores["b"] == pytest.approx(1.0 - expected_a, rel=1e-6)


def test_delta_stopping_uses_strict_less_than_and_actual_difference():
    adjacency = {"a": {"b": 1.0}, "b": {"a": 1.0}}

    scores = personalized_pagerank(
        adjacency,
        ["a"],
        alpha=0.5,
        iters=50,
        tol=0.5,
    )

    # Starting from (0.5, 0.5), the first update is (0.75, 0.25), whose
    # L1 delta is exactly 0.5. Strict comparison therefore permits one more
    # update, producing (0.625, 0.375).
    assert scores["a"] == pytest.approx(0.625, rel=1e-6)
    assert scores["b"] == pytest.approx(0.375, rel=1e-6)


class _HashChangingNode:
    def __init__(self):
        self._armed = False

    def __hash__(self):
        if self._armed:
            self._armed = False
            return 987654321
        return 123456789

    def __eq__(self, other):
        return self is other


class _ArmingAdjacency(dict):
    def get(self, key, default=None):
        value = super().get(key, default)
        if isinstance(key, _HashChangingNode):
            key._armed = True
        return value


def test_missing_out_sum_entry_is_treated_as_dangling_mass():
    node = _HashChangingNode()
    adjacency = _ArmingAdjacency({node: {}})

    scores = personalized_pagerank(adjacency, [], alpha=0.85, iters=3)

    # The adjacency lookup used while constructing out_sum deliberately makes
    # that dict's stored hash stale. The documented 0.0 fallback classifies
    # this node as dangling, and all rank mass teleports back to the sole node.
    assert scores[node] == pytest.approx(1.0, rel=1e-6)
