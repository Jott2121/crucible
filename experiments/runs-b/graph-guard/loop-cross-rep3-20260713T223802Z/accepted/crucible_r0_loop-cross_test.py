import math

import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


# ---------------------------------------------------------------------------
# node_specificity
# ---------------------------------------------------------------------------

def test_node_specificity_empty_adj():
    assert node_specificity({}) == {}


def test_node_specificity_degree_zero():
    result = node_specificity({"a": {}})
    # 1 / (1 + log(1 + 0)) = 1 / (1 + 0) = 1.0
    assert result["a"] == pytest.approx(1.0, rel=1e-9)


def test_node_specificity_degree_one():
    result = node_specificity({"a": {"b": 1.0}})
    expected = 1.0 / (1.0 + math.log(2.0))
    assert result["a"] == pytest.approx(expected, rel=1e-9)


def test_node_specificity_degree_three():
    result = node_specificity({"a": {"b": 1.0, "c": 1.0, "d": 1.0}})
    expected = 1.0 / (1.0 + math.log(4.0))
    assert result["a"] == pytest.approx(expected, rel=1e-9)


def test_node_specificity_only_keys_present_not_neighbors():
    # 'b' only appears as a neighbor value, not as a key of adj, so it should
    # not show up in the returned mapping.
    result = node_specificity({"a": {"b": 1.0}})
    assert set(result.keys()) == {"a"}
    assert "b" not in result


def test_node_specificity_higher_degree_lower_score():
    result = node_specificity({
        "low": {"x": 1.0},
        "high": {"x": 1.0, "y": 1.0, "z": 1.0, "w": 1.0},
    })
    assert result["low"] > result["high"]


def test_node_specificity_multiple_nodes_independent():
    adj = {"a": {}, "b": {"c": 1.0}}
    result = node_specificity(adj)
    assert result["a"] == pytest.approx(1.0, rel=1e-9)
    assert result["b"] == pytest.approx(1.0 / (1.0 + math.log(2.0)), rel=1e-9)


# ---------------------------------------------------------------------------
# personalized_pagerank
# ---------------------------------------------------------------------------

def test_ppr_empty_adj_returns_empty_dict():
    assert personalized_pagerank({}, []) == {}


def test_ppr_single_isolated_node_gets_all_mass():
    adj = {"a": {}}
    result = personalized_pagerank(adj, ["a"])
    assert result == pytest.approx({"a": 1.0}, rel=1e-9)


def test_ppr_sum_of_scores_is_one():
    adj = {
        "a": {"b": 1.0, "c": 2.0},
        "b": {"c": 1.0},
        "c": {"a": 1.0},
        "d": {},
    }
    result = personalized_pagerank(adj, ["a"])
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_all_scores_nonnegative():
    adj = {
        "a": {"b": 1.0},
        "b": {"a": 1.0, "c": 1.0},
        "c": {},
    }
    result = personalized_pagerank(adj, ["b"])
    for score in result.values():
        assert score >= 0.0


def test_ppr_dangling_seed_absorbing_closed_form():
    # a -> b (weight 1), b has no outgoing edges; personalize on 'a'.
    # Closed form fixed point: rank_a = 1/(1+alpha), rank_b = alpha/(1+alpha)
    alpha = 0.85
    adj = {"a": {"b": 1.0}, "b": {}}
    result = personalized_pagerank(adj, ["a"], alpha=alpha, iters=200, tol=1e-12)
    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha / (1.0 + alpha)
    assert result["a"] == pytest.approx(expected_a, rel=1e-6)
    assert result["b"] == pytest.approx(expected_b, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_symmetric_two_node_cycle_closed_form():
    # a <-> b mutual edges, personalize on 'a'.
    # Closed form fixed point: rank_a = 1/(1+alpha), rank_b = alpha/(1+alpha)
    alpha = 0.85
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, ["a"], alpha=alpha, iters=200, tol=1e-12)
    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha / (1.0 + alpha)
    assert result["a"] == pytest.approx(expected_a, rel=1e-6)
    assert result["b"] == pytest.approx(expected_b, rel=1e-6)


def test_ppr_no_edges_uniform_teleport_stays_uniform():
    # No outgoing edges anywhere -> everything is dangling; with no valid
    # seeds, teleport falls back to uniform over all nodes, and the uniform
    # distribution is already the fixed point.
    adj = {"a": {}, "b": {}}
    result = personalized_pagerank(adj, [])
    assert result["a"] == pytest.approx(0.5, rel=1e-9)
    assert result["b"] == pytest.approx(0.5, rel=1e-9)


def test_ppr_seeds_not_in_graph_falls_back_to_uniform():
    # Seeds that don't exist in the graph should behave like no seeds at all
    # (uniform teleport / plain PageRank).
    adj = {"a": {}, "b": {}}
    result = personalized_pagerank(adj, ["nonexistent"])
    assert result["a"] == pytest.approx(0.5, rel=1e-9)
    assert result["b"] == pytest.approx(0.5, rel=1e-9)


def test_ppr_includes_nodes_only_referenced_as_neighbors():
    # 'c' is never a key of adj but appears as a neighbor; it must still
    # appear in the result.
    adj = {"a": {"c": 1.0}}
    result = personalized_pagerank(adj, ["a"])
    assert "c" in result
    assert set(result.keys()) == {"a", "c"}


def test_ppr_seed_node_scores_higher_than_isolated_nonseed():
    # In a graph where one node is fully isolated (no in/out edges beyond
    # itself referenced), the seeded connected node should outrank it once
    # teleport mass concentrates there.
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}, "c": {}}
    result = personalized_pagerank(adj, ["a"])
    assert result["a"] > result["c"]
    assert result["b"] > result["c"]


def test_ppr_scores_sum_to_one_with_multiple_seeds():
    adj = {
        "a": {"b": 1.0},
        "b": {"c": 1.0},
        "c": {"a": 1.0},
    }
    result = personalized_pagerank(adj, ["a", "b"])
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)

