import pytest
from graph_guard.ppr import personalized_pagerank

def _self_loop_and_dangling_after(steps, alpha):
    """Independently compute PPR for a -> a and dangling b, seeded at a."""
    a = 0.5
    b = 0.5
    for _ in range(steps):
        next_a = alpha * a + (1.0 - alpha) + alpha * b
        next_b = alpha * a
        a, b = (next_a, next_b)
    return (a, b)

def test_duplicate_seeds_are_aggregated_into_a_normalized_teleport_distribution():
    result = personalized_pagerank({'only': {}}, ['only', 'only'], alpha=0.85, iters=1, tol=0.0)
    assert result['only'] == pytest.approx(1.0, rel=1e-12)

class _DefaultSensitiveAdjacency(dict):
    """A dict subclass that requires callers to provide a mapping fallback."""

    def get(self, key, default=None):
        if default is None:
            return None
        return super().get(key, default)

def test_adjacency_lookup_uses_an_empty_mapping_fallback_for_outgoing_edges():
    adjacency = _DefaultSensitiveAdjacency({'a': {'a': 1.0}})
    result = personalized_pagerank(adjacency, ['a'], alpha=0.5, iters=1, tol=0.0)
    assert result['a'] == pytest.approx(1.0, rel=1e-12)
