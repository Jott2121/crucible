import math
import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


# ---------------------------------------------------------------------------
# personalized_pagerank
# ---------------------------------------------------------------------------

def test_ppr_empty_adj_returns_empty_dict():
    assert personalized_pagerank({}, []) == {}


def test_ppr_single_self_loop_node_converges_to_one():
    adj = {"a": {"a": 1.0}}
    result = personalized_pagerank(adj, ["a"])
    assert result.keys() == {"a"}
    assert result["a"] == pytest.approx(1.0, rel=1e-6)


def test_ppr_two_isolated_nodes_seed_dominates_exactly():
    # Both nodes are dangling (no outgoing edges), seed is 'a'.
    adj = {"a": {}, "b": {}}
    result = personalized_pagerank(adj, ["a"])
    assert result["a"] == pytest.approx(1.0, rel=1e-6)
    assert result["b"] == pytest.approx(0.0, abs=1e-9)


def test_ppr_symmetric_two_node_absent_seed_uniform():
    # Seed not present in graph -> falls back to uniform teleport (plain PageRank).
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, ["z"])
    assert result["a"] == pytest.approx(0.5, rel=1e-6)
    assert result["b"] == pytest.approx(0.5, rel=1e-6)


def test_ppr_zero_iters_returns_initial_uniform_distribution():
    adj = {"a": {"b": 1.0}, "b": {}}
    result = personalized_pagerank(adj, ["a"], iters=0)
    assert result["a"] == pytest.approx(0.5, rel=1e-6)
    assert result["b"] == pytest.approx(0.5, rel=1e-6)


def test_ppr_scores_sum_to_one_for_asymmetric_graph():
    adj = {
        "a": {"b": 1.0, "c": 2.0},
        "b": {"c": 1.0},
        "c": {"a": 1.0},
    }
    result = personalized_pagerank(adj, ["a"])
    total = sum(result.values())
    assert total == pytest.approx(1.0, rel=1e-6)
    assert set(result.keys()) == {"a", "b", "c"}


def test_ppr_all_nodes_are_nonnegative():
    adj = {
        "x": {"y": 1.0},
        "y": {"z": 1.0},
        "z": {"x": 1.0},
        "w": {},  # dangling node, only referenced nowhere else
    }
    result = personalized_pagerank(adj, ["x"])
    for v in result.values():
        assert v >= -1e-12


def test_ppr_includes_neighbor_only_node_not_in_adj_keys():
    # 'b' appears only as a neighbor, never as a key in adj.
    adj = {"a": {"b": 1.0}}
    result = personalized_pagerank(adj, ["a"])
    assert set(result.keys()) == {"a", "b"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_seed_gets_more_mass_than_far_node_in_chain():
    # Chain a -> b -> c, personalize on 'a'; 'a' should end up with more
    # score than the farthest node 'c' due to teleport bias.
    adj = {"a": {"b": 1.0}, "b": {"c": 1.0}, "c": {}}
    result = personalized_pagerank(adj, ["a"])
    assert result["a"] > result["c"]


def test_ppr_empty_seeds_falls_back_to_all_nodes():
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result_empty_seeds = personalized_pagerank(adj, [])
    result_absent_seed = personalized_pagerank(adj, ["nonexistent"])
    assert result_empty_seeds["a"] == pytest.approx(result_absent_seed["a"], rel=1e-6)
    assert result_empty_seeds["b"] == pytest.approx(result_absent_seed["b"], rel=1e-6)


# ---------------------------------------------------------------------------
# node_specificity
# ---------------------------------------------------------------------------

def test_node_specificity_empty_adj():
    assert node_specificity({}) == {}


def test_node_specificity_zero_degree_node_is_one():
    adj = {"a": {}}
    result = node_specificity(adj)
    expected = 1.0 / (1.0 + math.log(1.0 + 0))
    assert result["a"] == pytest.approx(expected, rel=1e-6)
    assert result["a"] == pytest.approx(1.0, rel=1e-6)


def test_node_specificity_degree_one_node():
    adj = {"a": {"b": 1.0}}
    result = node_specificity(adj)
    expected = 1.0 / (1.0 + math.log(1.0 + 1))
    assert result["a"] == pytest.approx(expected, rel=1e-6)


def test_node_specificity_degree_two_node():
    adj = {"a": {"b": 1.0, "c": 1.0}, "b": {}}
    result = node_specificity(adj)
    expected_a = 1.0 / (1.0 + math.log(1.0 + 2))
    expected_b = 1.0 / (1.0 + math.log(1.0 + 0))
    assert result["a"] == pytest.approx(expected_a, rel=1e-6)
    assert result["b"] == pytest.approx(expected_b, rel=1e-6)


def test_node_specificity_only_covers_keys_present_in_adj():
    # Nodes appearing only as neighbors (not as top-level keys) are not
    # included in the output, per the docstring's assumption of symmetric adj.
    adj = {"a": {"b": 1.0}}
    result = node_specificity(adj)
    assert set(result.keys()) == {"a"}


def test_node_specificity_monotonically_decreases_with_degree():
    adj = {
        "low": {"x": 1.0},
        "high": {"x": 1.0, "y": 1.0, "z": 1.0, "w": 1.0},
    }
    result = node_specificity(adj)
    assert result["low"] > result["high"]


def test_node_specificity_values_bounded_between_zero_and_one():
    adj = {"a": {f"n{i}": 1.0 for i in range(10)}}
    result = node_specificity(adj)
    assert 0.0 < result["a"] < 1.0
