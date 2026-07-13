import pytest

from graph_guard.ppr import personalized_pagerank


def test_duplicate_seed_occurrences_preserve_all_teleport_probability():
    result = personalized_pagerank(
        {"seed": {}},
        ["seed", "seed"],
        alpha=0.5,
        iters=1,
        tol=0.0,
    )

    # A dangling singleton redistributes all mass according to teleport.
    # Repeated valid seeds still describe a probability distribution totaling one.
    assert result["seed"] == pytest.approx(1.0, rel=1e-6)


def test_default_iteration_count_and_tolerance_produce_fifty_step_ppr():
    adjacency = {
        "a": {"b": 1.0},
        "b": {"a": 1.0},
    }

    result = personalized_pagerank(adjacency, ["a"])

    # For this two-node graph, with x_k = rank(a),
    # x_(k+1) = (1 - alpha) + alpha * (1 - x_k), x_0 = 1/2.
    alpha = 0.85
    fixed_point = 1.0 / (1.0 + alpha)
    expected_a = fixed_point + (0.5 - fixed_point) * ((-alpha) ** 50)
    expected_b = 1.0 - expected_a

    assert result["a"] == pytest.approx(expected_a, rel=1e-9)
    assert result["b"] == pytest.approx(expected_b, rel=1e-9)


def test_delta_uses_difference_so_large_tolerance_stops_after_first_step():
    result = personalized_pagerank(
        {"a": {"b": 1.0}, "b": {"a": 1.0}},
        ["a"],
        alpha=0.5,
        iters=5,
        tol=0.6,
    )

    # Initial ranks are (0.5, 0.5).  After one step they are (0.75, 0.25),
    # whose L1 change is 0.5 and therefore below the supplied tolerance.
    assert result["a"] == pytest.approx(0.75, rel=1e-6)
    assert result["b"] == pytest.approx(0.25, rel=1e-6)


def test_strict_tolerance_comparison_continues_when_delta_equals_tolerance():
    result = personalized_pagerank(
        {"a": {"b": 1.0}, "b": {"a": 1.0}},
        ["a"],
        alpha=0.5,
        iters=2,
        tol=0.5,
    )

    # The first step has delta exactly 0.5, so strict "<" must not stop.
    # The second step from (0.75, 0.25) yields (0.625, 0.375).
    assert result["a"] == pytest.approx(0.625, rel=1e-6)
    assert result["b"] == pytest.approx(0.375, rel=1e-6)


class _VanishingRowDict(dict):
    """A dict subclass whose row disappears after out_sum has been calculated."""

    def __init__(self):
        super().__init__({"a": {"a": 1.0}})
        self.get_calls = 0

    def get(self, key, default=None):
        self.get_calls += 1
        if self.get_calls == 1:
            return super().get(key, default)
        return default


def test_missing_row_after_positive_out_sum_is_treated_as_empty_row():
    adjacency = _VanishingRowDict()

    result = personalized_pagerank(
        adjacency,
        ["a"],
        alpha=0.5,
        iters=1,
        tol=0.0,
    )

    # The first lookup establishes an outgoing weight of one; the later row
    # lookup is absent and must use the documented empty-adjacency fallback.
    # Thus no edge receives rank mass and only teleport mass remains.
    assert result["a"] == pytest.approx(0.5, rel=1e-6)
