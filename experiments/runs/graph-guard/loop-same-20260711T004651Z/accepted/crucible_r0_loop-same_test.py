import math
import pytest
from graph_guard.ppr import personalized_pagerank, node_specificity

def test_empty_graph_returns_empty_dict():
    assert personalized_pagerank({}, []) == {}
    assert personalized_pagerank({}, ['a']) == {}

def test_single_node_no_edges():
    result = personalized_pagerank({'a': {}}, ['a'])
    assert result == pytest.approx({'a': 1.0}, abs=1e-09)

def test_single_node_self_loop():
    result = personalized_pagerank({'a': {'a': 1.0}}, ['a'])
    assert result == pytest.approx({'a': 1.0}, abs=1e-09)

def test_two_disconnected_nodes_seed_gets_all_mass():
    result = personalized_pagerank({'a': {}, 'b': {}}, ['a'])
    assert result['a'] == pytest.approx(1.0, abs=1e-09)
    assert result['b'] == pytest.approx(0.0, abs=1e-09)

def test_alpha_zero_gives_pure_teleport_distribution():
    adj = {'a': {'b': 2.0}, 'b': {'c': 1.0}, 'c': {}}
    result = personalized_pagerank(adj, ['a', 'b'], alpha=0)
    assert result['a'] == pytest.approx(0.5, abs=1e-09)
    assert result['b'] == pytest.approx(0.5, abs=1e-09)
    assert result['c'] == pytest.approx(0.0, abs=1e-09)

def test_alpha_zero_no_valid_seeds_uniform_teleport():
    adj = {'a': {'b': 1.0}, 'b': {}, 'c': {}}
    result = personalized_pagerank(adj, ['z'], alpha=0)
    assert result['a'] == pytest.approx(1.0 / 3.0, abs=1e-09)
    assert result['b'] == pytest.approx(1.0 / 3.0, abs=1e-09)
    assert result['c'] == pytest.approx(1.0 / 3.0, abs=1e-09)

def test_empty_seeds_falls_back_to_uniform_teleport():
    adj = {'a': {'b': 1.0}, 'b': {}, 'c': {}}
    result = personalized_pagerank(adj, [], alpha=0)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-06)
    assert result['a'] == pytest.approx(1.0 / 3.0, abs=1e-09)
    assert result['b'] == pytest.approx(1.0 / 3.0, abs=1e-09)
    assert result['c'] == pytest.approx(1.0 / 3.0, abs=1e-09)

def test_node_referenced_only_as_neighbor_is_included():
    adj = {'a': {'b': 5.0}}
    result = personalized_pagerank(adj, ['a'], alpha=0)
    assert set(result.keys()) == {'a', 'b'}
    assert result['a'] == pytest.approx(1.0, abs=1e-09)
    assert result['b'] == pytest.approx(0.0, abs=1e-09)

def test_isolated_non_seed_node_gets_zero_score():
    adj = {'a': {'b': 1.0}, 'b': {'a': 1.0}, 'c': {}}
    result = personalized_pagerank(adj, ['a'])
    assert result['c'] == pytest.approx(0.0, abs=1e-09)

def test_scores_sum_to_one_and_are_nonnegative():
    adj = {'a': {'b': 1.0, 'c': 2.0}, 'b': {'c': 1.0}, 'c': {'a': 0.5}, 'd': {}}
    result = personalized_pagerank(adj, ['a', 'd'])
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-06)
    for v in result.values():
        assert v >= 0.0

def test_seed_node_outranks_unrelated_isolated_node():
    adj = {'a': {'b': 1.0}, 'b': {'a': 1.0}, 'isolated': {}}
    result = personalized_pagerank(adj, ['a'])
    assert result['a'] > result['isolated']
    assert result['b'] > result['isolated']

def test_node_specificity_empty_graph():
    assert node_specificity({}) == {}

def test_node_specificity_degree_zero_is_one():
    result = node_specificity({'a': {}})
    assert result['a'] == pytest.approx(1.0, rel=1e-09)

def test_node_specificity_formula_matches_manual_computation():
    adj = {'a': {}, 'b': {'a': 1.0, 'c': 1.0}}
    result = node_specificity(adj)
    expected_a = 1.0 / (1.0 + math.log(1.0 + 0))
    expected_b = 1.0 / (1.0 + math.log(1.0 + 2))
    assert result['a'] == pytest.approx(expected_a, rel=1e-09)
    assert result['b'] == pytest.approx(expected_b, rel=1e-09)

def test_node_specificity_only_includes_adjacency_keys():
    adj = {'a': {'z': 1.0}}
    result = node_specificity(adj)
    assert set(result.keys()) == {'a'}

def test_node_specificity_higher_degree_means_lower_score():
    adj = {'hub': {'n1': 1.0, 'n2': 1.0, 'n3': 1.0, 'n4': 1.0}, 'leaf': {'n1': 1.0}}
    result = node_specificity(adj)
    assert result['hub'] < result['leaf']
    assert 0.0 < result['hub'] <= 1.0
    assert 0.0 < result['leaf'] <= 1.0
