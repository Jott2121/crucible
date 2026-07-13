import math

import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


# ---------------------------------------------------------------------------
# personalized_pagerank
# ---------------------------------------------------------------------------

def test_ppr_empty_adj_returns_empty_dict():
    assert personalized_pagerank({}, ["a"]) == {}


def test_ppr_empty_adj_empty_seeds_returns_empty_dict():
    assert personalized_pagerank({}, []) == {}


def test_ppr_single_node_no_edges_self_seed():
    adj = {"a": {}}
    result = personalized_pagerank(adj, ["a"])
    assert result == pytest.approx({"a": 1.0}, abs=1e-9)


def test_ppr_two_node_directed_edge_fixed_point():
    # a -> b (weight 1), seed on 'a'.
    # Analytic fixed point: rank_a = 1/(1+alpha), rank_b = alpha/(1+alpha)
    adj = {"a": {"b": 1.0}, "b": {}}
    alpha = 0.85
    result = personalized_pagerank(adj, ["a"], alpha=alpha)
    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha / (1.0 + alpha)
    assert result["a"] == pytest.approx(expected_a, abs=1e-3)
    assert result["b"] == pytest.approx(expected_b, abs=1e-3)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_symmetric_graph_no_seeds_uniform_split():
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, [])
    assert result["a"] == pytest.approx(0.5, rel=1e-6)
    assert result["b"] == pytest.approx(0.5, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_invalid_seed_falls_back_to_uniform_teleport():
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, ["does-not-exist"])
    assert result["a"] == pytest.approx(0.5, rel=1e-6)
    assert result["b"] == pytest.approx(0.5, rel=1e-6)


def test_ppr_sums_to_one_and_nonnegative_on_cycle():
    adj = {
        "a": {"b": 1.0},
        "b": {"c": 1.0},
        "c": {"a": 1.0},
    }
    result = personalized_pagerank(adj, ["a"])
    assert set(result.keys()) == {"a", "b", "c"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    for v in result.values():
        assert v >= 0.0


def test_ppr_alpha_zero_yields_pure_teleport_distribution():
    adj = {"a": {"b": 1.0}, "b": {}}
    result = personalized_pagerank(adj, ["b"], alpha=0.0)
    assert result["a"] == pytest.approx(0.0, abs=1e-9)
    assert result["b"] == pytest.approx(1.0, abs=1e-9)


def test_ppr_alpha_zero_multi_seed_uniform_split():
    adj = {"a": {}, "b": {}, "c": {}}
    result = personalized_pagerank(adj, ["a", "b"], alpha=0.0)
    assert result["a"] == pytest.approx(0.5, abs=1e-9)
    assert result["b"] == pytest.approx(0.5, abs=1e-9)
    assert result["c"] == pytest.approx(0.0, abs=1e-9)


def test_ppr_includes_neighbor_only_nodes():
    # 'b' only appears as a neighbor value, never as a top-level key.
    adj = {"a": {"b": 1.0}}
    result = personalized_pagerank(adj, ["a"])
    assert set(result.keys()) == {"a", "b"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# node_specificity
# ---------------------------------------------------------------------------

def test_node_specificity_empty_adj():
    assert node_specificity({}) == {}


def test_node_specificity_zero_degree_is_one():
    adj = {"z": {}}
    result = node_specificity(adj)
    assert result["z"] == pytest.approx(1.0, abs=1e-9)


def test_node_specificity_exact_values():
    adj = {
        "a": {},
        "b": {"a": 1.0, "c": 2.0},
        "c": {"b": 1.0},
    }
    result = node_specificity(adj)
    expected_a = 1.0 / (1.0 + math.log(1.0 + 0))
    expected_b = 1.0 / (1.0 + math.log(1.0 + 2))
    expected_c = 1.0 / (1.0 + math.log(1.0 + 1))
    assert result["a"] == pytest.approx(expected_a, rel=1e-9)
    assert result["b"] == pytest.approx(expected_b, rel=1e-9)
    assert result["c"] == pytest.approx(expected_c, rel=1e-9)


def test_node_specificity_monotonic_with_degree():
    adj = {
        "low_degree": {"n1": 1.0},
        "high_degree": {"n1": 1.0, "n2": 1.0, "n3": 1.0, "n4": 1.0, "n5": 1.0},
    }
    result = node_specificity(adj)
    expected_low = 1.0 / (1.0 + math.log(1.0 + 1))
    expected_high = 1.0 / (1.0 + math.log(1.0 + 5))
    assert result["low_degree"] == pytest.approx(expected_low, rel=1e-9)
    assert result["high_degree"] == pytest.approx(expected_high, rel=1e-9)
    assert result["low_degree"] > result["high_degree"]


def test_node_specificity_only_over_top_level_keys():
    # 'nbr' is referenced only as a neighbor; it should not get its own entry.
    adj = {"a": {"nbr": 1.0}}
    result = node_specificity(adj)
    assert set(result.keys()) == {"a"}
