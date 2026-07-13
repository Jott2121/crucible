import pytest
from graph_guard.ppr import personalized_pagerank

def test_pagerank_trivial_single_dangling_node_returns_full_mass():
    adj = {'A': {}}
    result = personalized_pagerank(adj, seeds=['A'], alpha=0.85, iters=50, tol=1e-09)
    assert result == {'A': pytest.approx(1.0, abs=1e-09)}

def test_pagerank_mass_conserved_with_mixed_dangling_and_normal_nodes():
    adj = {'A': {'B': 1.0}, 'B': {'C': 1.0}}
    result = personalized_pagerank(adj, seeds=['A'], alpha=0.85, iters=50, tol=1e-09)
    assert set(result.keys()) == {'A', 'B', 'C'}
    assert sum(result.values()) == pytest.approx(1.0, abs=1e-06)
    for v in ('A', 'B', 'C'):
        assert result[v] > 0.0
