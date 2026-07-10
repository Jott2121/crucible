import pytest
from graph_guard.ppr import personalized_pagerank

def test_duplicate_seeds_receive_their_combined_teleport_probability():
    result = personalized_pagerank({'seed': {}}, ['seed', 'seed'], alpha=0.5, iters=1, tol=0.0)
    assert result['seed'] == pytest.approx(1.0, rel=1e-12)

def test_default_iteration_count_is_fifty_when_tolerance_cannot_stop_early():
    alpha = 0.99
    result = personalized_pagerank({'a': {'b': 1.0}, 'b': {}}, ['a'], alpha=alpha, tol=0.0)
    expected_a = 0.5
    for _ in range(50):
        expected_a = 1.0 - alpha * expected_a
    assert result['a'] == pytest.approx(expected_a, rel=1e-10)
    assert result['b'] == pytest.approx(1.0 - expected_a, rel=1e-10)

def test_convergence_delta_uses_difference_not_sum():
    result = personalized_pagerank({'a': {'b': 1.0}, 'b': {}}, ['a'], alpha=0.5, iters=2, tol=0.6)
    assert result['a'] == pytest.approx(0.75, rel=1e-12)
    assert result['b'] == pytest.approx(0.25, rel=1e-12)

def test_equality_with_tolerance_does_not_stop_iteration():
    result = personalized_pagerank({'a': {'b': 1.0}, 'b': {}}, ['a'], alpha=0.5, iters=2, tol=0.5)
    assert result['a'] == pytest.approx(0.625, rel=1e-12)
    assert result['b'] == pytest.approx(0.375, rel=1e-12)

class _HashChangingNode:

    def __init__(self, name):
        self.name = name
        self.hash_value = hash(name)

    def __hash__(self):
        return self.hash_value

    def __eq__(self, other):
        return self is other

class _HashFlippingAdjacency(dict):
    """Changes key hashes after out_sum has been built."""

    def __init__(self, first, second):
        super().__init__({first: {}, second: {}})
        self._nodes = (first, second)
        self._get_calls = 0

    def get(self, key, default=None):
        value = super().get(key, default)
        self._get_calls += 1
        if self._get_calls == 2:
            for node in self._nodes:
                node.hash_value += 1000003
        return value

class _ExpiringRowsAdjacency(dict):
    """Supplies a positive row while sums are built, then only supplied defaults."""

    def __init__(self):
        super().__init__({'source': {}, 'sink': {}})
        self._sum_phase_calls = 0

    def get(self, key, default=None):
        if self._sum_phase_calls < 2:
            self._sum_phase_calls += 1
            if key == 'source':
                return {'sink': 1.0}
            return {}
        return default
