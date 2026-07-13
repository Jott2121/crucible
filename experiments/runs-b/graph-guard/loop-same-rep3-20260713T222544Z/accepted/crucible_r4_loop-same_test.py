import pytest
from graph_guard.ppr import personalized_pagerank

def test_ppr_missing_key_matches_explicit_empty_dict():
    adj_omitted = {'a': {'b': 1.0}}
    adj_explicit = {'a': {'b': 1.0}, 'b': {}}
    r1 = personalized_pagerank(adj_omitted, seeds=['a'], alpha=0.85, iters=50, tol=1e-09)
    r2 = personalized_pagerank(adj_explicit, seeds=['a'], alpha=0.85, iters=50, tol=1e-09)
    assert r1['a'] == pytest.approx(r2['a'], rel=1e-09)
    assert r1['b'] == pytest.approx(r2['b'], rel=1e-09)

def test_ppr_symmetric_graph_uniform_teleport_is_exact_fixed_point():
    adj = {'a': {'b': 1.0}, 'b': {'a': 1.0}}
    result = personalized_pagerank(adj, seeds=[], alpha=0.85, iters=50, tol=1e-09)
    assert result['a'] == pytest.approx(0.5, abs=1e-09)
    assert result['b'] == pytest.approx(0.5, abs=1e-09)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-09)
