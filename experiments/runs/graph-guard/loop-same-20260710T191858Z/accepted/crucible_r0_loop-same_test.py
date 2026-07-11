import math
import pytest
from graph_guard.ppr import personalized_pagerank, node_specificity

def test_ppr_empty_graph_returns_empty_dict():
    assert personalized_pagerank({}, []) == {}

def test_ppr_empty_graph_with_seeds_still_empty():
    assert personalized_pagerank({}, ['x', 'y']) == {}

def test_ppr_single_isolated_node_gets_full_mass():
    adj = {'a': {}}
    result = personalized_pagerank(adj, ['a'])
    assert set(result.keys()) == {'a'}
    assert result['a'] == pytest.approx(1.0, rel=1e-09)

def test_ppr_symmetric_graph_absent_seeds_uniform():
    adj = {'a': {'b': 1.0}, 'b': {'a': 1.0}}
    result = personalized_pagerank(adj, ['not_in_graph'])
    assert result['a'] == pytest.approx(0.5, rel=1e-09)
    assert result['b'] == pytest.approx(0.5, rel=1e-09)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-09)

def test_ppr_alpha_zero_equals_pure_teleport():
    adj = {'a': {'b': 2.0}, 'b': {}}
    result = personalized_pagerank(adj, ['a'], alpha=0.0)
    assert result['a'] == pytest.approx(1.0, rel=1e-09)
    assert result['b'] == pytest.approx(0.0, abs=1e-09)

def test_ppr_scores_sum_to_one_for_larger_graph():
    adj = {'a': {'b': 1.0, 'c': 2.0}, 'b': {'c': 1.0}, 'c': {'a': 1.0}, 'd': {}}
    result = personalized_pagerank(adj, ['a', 'd'])
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-06)
    assert set(result.keys()) == {'a', 'b', 'c', 'd'}
    for v in result.values():
        assert v >= 0.0

def test_ppr_nodes_only_appearing_as_neighbors_are_included():
    adj = {'a': {'z': 1.0}}
    result = personalized_pagerank(adj, ['a'])
    assert set(result.keys()) == {'a', 'z'}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-06)

def test_ppr_seed_outside_graph_falls_back_to_all_nodes_uniform_teleport():
    adj = {'a': {'b': 1.0}, 'b': {'c': 1.0}, 'c': {}}
    result = personalized_pagerank(adj, ['nonexistent_seed'])
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-06)
    for v in result.values():
        assert v >= 0.0

def test_ppr_iters_zero_returns_uniform_initial_rank():
    adj = {'a': {'b': 1.0}, 'b': {'a': 1.0}, 'c': {}}
    result = personalized_pagerank(adj, ['a'], iters=0)
    assert result['a'] == pytest.approx(1.0 / 3.0, rel=1e-09)
    assert result['b'] == pytest.approx(1.0 / 3.0, rel=1e-09)
    assert result['c'] == pytest.approx(1.0 / 3.0, rel=1e-09)

def test_node_specificity_empty_graph():
    assert node_specificity({}) == {}

def test_node_specificity_zero_degree_node_is_one():
    adj = {'a': {}}
    result = node_specificity(adj)
    assert result['a'] == pytest.approx(1.0, rel=1e-09)

def test_node_specificity_only_includes_adj_keys():
    adj = {'a': {'b': 1.0, 'c': 1.0}, 'b': {'a': 1.0}}
    result = node_specificity(adj)
    assert set(result.keys()) == {'a', 'b'}

def test_node_specificity_exact_values():
    adj = {'a': {'b': 1.0, 'c': 1.0}, 'b': {'a': 1.0}}
    result = node_specificity(adj)
    expected_a = 1.0 / (1.0 + math.log(1.0 + 2))
    expected_b = 1.0 / (1.0 + math.log(1.0 + 1))
    assert result['a'] == pytest.approx(expected_a, rel=1e-09)
    assert result['b'] == pytest.approx(expected_b, rel=1e-09)

def test_node_specificity_decreases_with_degree():
    adj = {'hub': {'n1': 1.0, 'n2': 1.0, 'n3': 1.0, 'n4': 1.0}, 'leaf': {'n1': 1.0}}
    result = node_specificity(adj)
    assert result['hub'] < result['leaf']
    assert 0.0 < result['hub'] <= 1.0
    assert 0.0 < result['leaf'] <= 1.0
