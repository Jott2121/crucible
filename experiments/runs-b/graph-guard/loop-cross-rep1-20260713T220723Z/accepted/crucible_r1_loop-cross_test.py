import pytest
from graph_guard.ppr import personalized_pagerank

def test_default_iteration_count_and_tolerance_produce_fifty_step_cycle_rank():
    alpha = 0.85
    adjacency = {'a': {'b': 1.0}, 'b': {'a': 1.0}}
    result = personalized_pagerank(adjacency, ['a'])
    stationary_a = 1.0 / (1.0 + alpha)
    expected_a = stationary_a + (-alpha) ** 50 * (0.5 - stationary_a)
    assert result['a'] == pytest.approx(expected_a, rel=1e-06)
    assert result['b'] == pytest.approx(1.0 - expected_a, rel=1e-06)

def test_duplicate_seeds_are_accumulated_into_a_normalized_teleport_distribution():
    result = personalized_pagerank({'a': {}, 'b': {}}, ['a', 'a'], alpha=0.5, iters=1)
    assert result['a'] == pytest.approx(1.0, rel=1e-06)
    assert result['b'] == pytest.approx(0.0, abs=1e-12)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-06)

def test_delta_equal_to_tolerance_does_not_stop_until_a_later_iteration():
    result = personalized_pagerank({'a': {'b': 1.0}, 'b': {'a': 1.0}}, ['a'], alpha=0.5, iters=3, tol=0.5)
    assert result['a'] == pytest.approx(0.625, rel=1e-06)
    assert result['b'] == pytest.approx(0.375, rel=1e-06)

class _MutableHashNode:

    def __init__(self, name):
        self.name = name
        self.hash_value = hash(name)

    def __hash__(self):
        return self.hash_value

    def __eq__(self, other):
        return self is other

class _HashChangingAdjacency(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_calls = 0
        self.first_lookup_node = None

    def get(self, key, default=None):
        self.get_calls += 1
        if self.get_calls == 1:
            self.first_lookup_node = key
        elif self.get_calls == 2:
            self.first_lookup_node.hash_value += 1
        return super().get(key, default)

class _VanishingAdjacency(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_calls = 0

    def get(self, key, default=None):
        self.get_calls += 1
        if self.get_calls <= 2:
            return super().get(key, default)
        return default

def test_missing_row_after_outgoing_weight_calculation_uses_empty_adjacency():
    adjacency = _VanishingAdjacency({'a': {'a': 1.0}, 'b': {'b': 1.0}})
    result = personalized_pagerank(adjacency, ['a'], alpha=0.5, iters=1)
    assert result['a'] == pytest.approx(0.5, rel=1e-06)
    assert result['b'] == pytest.approx(0.0, abs=1e-12)
    assert sum(result.values()) == pytest.approx(0.5, rel=1e-06)
