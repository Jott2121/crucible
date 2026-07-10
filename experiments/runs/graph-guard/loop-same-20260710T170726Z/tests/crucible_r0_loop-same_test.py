"""Tests for graph_guard.ppr (Personalized PageRank + node specificity)."""
import math

import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


# ---------------------------------------------------------------------------
# personalized_pagerank
# ---------------------------------------------------------------------------

def test_empty_adj_returns_empty_dict():
    assert personalized_pagerank({}, []) == {}


def test_single_isolated_node_gets_full_mass():
    adj = {"a": {}}
    result = personalized_pagerank(adj, ["a"])
    assert result.keys() == {"a"}
    assert result["a"] == pytest.approx(1.0, abs=1e-9)


def test_single_isolated_node_empty_seeds_falls_back_uniform():
    # seeds=[] -> no valid seeds -> fallback to uniform over all nodes,
    # which for a single node is trivially that node itself.
    adj = {"a": {}}
    result = personalized_pagerank(adj, [])
    assert result["a"] == pytest.approx(1.0, abs=1e-9)


def test_nodes_include_targets_not_present_as_keys():
    adj = {"a": {"b": 2.0}}
    result = personalized_pagerank(adj, ["a"])
    assert set(result.keys()) == {"a", "b"}


def test_two_node_graph_one_iteration_exact_values():
    # a -> b with weight 1.0, seed = 'a', alpha default 0.85, single iteration.
    adj = {"a": {"b": 1.0}, "b": {}}
    result = personalized_pagerank(adj, ["a"], iters=1)
    # Manually derived: rank0 = {'a':0.5,'b':0.5}
    # nxt['b'] = 0.85*0.5*1 = 0.425 ; dangling from b = 0.5
    # mass = 0.15 + 0.85*0.5 = 0.575 ; nxt['a'] = 0.575 (all teleport mass to 'a')
    assert result["a"] == pytest.approx(0.575, rel=1e-9)
    assert result["b"] == pytest.approx(0.425, rel=1e-9)
    assert (result["a"] + result["b"]) == pytest.approx(1.0, rel=1e-9)


def test_symmetric_graph_absent_seed_falls_back_uniform_teleport():
    # seed not present in graph -> valid seeds become all nodes -> teleport is uniform.
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, ["nonexistent"], iters=1)
    # By symmetry, both nodes end up with exactly 0.5 after one iteration.
    assert result["a"] == pytest.approx(0.5, rel=1e-9)
    assert result["b"] == pytest.approx(0.5, rel=1e-9)


def test_alpha_zero_collapses_to_pure_teleport_distribution():
    # With alpha=0, diffusion contributes nothing; rank converges to the
    # teleport (seed) distribution exactly.
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, ["a"], alpha=0.0)
    assert result["a"] == pytest.approx(1.0, abs=1e-9)
    assert result["b"] == pytest.approx(0.0, abs=1e-9)


def test_scores_sum_to_one_default_params():
    adj = {
        "a": {"b": 1.0, "c": 2.0},
        "b": {"c": 1.0},
        "c": {"a": 1.0},
        "d": {},  # dangling node
    }
    result = personalized_pagerank(adj, ["a", "d"])
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    assert set(result.keys()) == {"a", "b", "c", "d"}


def test_all_scores_nonnegative():
    adj = {
        "a": {"b": 5.0},
        "b": {"a": 1.0, "c": 3.0},
        "c": {},
    }
    result = personalized_pagerank(adj, ["b"])
    for v in result.values():
        assert v >= 0.0


def test_seed_weighting_favors_seeded_node_over_non_seeded_isolated_node():
    # A node that receives no incoming edges and is not a seed should score
    # lower than the seeded node in a simple two-node disconnected setup.
    adj = {"seed": {}, "other": {}}
    result = personalized_pagerank(adj, ["seed"])
    assert result["seed"] > result["other"]
    assert result["seed"] == pytest.approx(1.0, abs=1e-9)
    assert result["other"] == pytest.approx(0.0, abs=1e-9)


def test_invalid_seeds_not_in_graph_fallback_to_uniform_over_all_nodes():
    adj = {"x": {}, "y": {}}
    result = personalized_pagerank(adj, ["absent_seed"], iters=1)
    # Both are isolated (dangling), teleport uniform over {'x','y'} -> equal scores.
    assert result["x"] == pytest.approx(0.5, rel=1e-9)
    assert result["y"] == pytest.approx(0.5, rel=1e-9)


# ---------------------------------------------------------------------------
# node_specificity
# ---------------------------------------------------------------------------

def test_node_specificity_empty_adj():
    assert node_specificity({}) == {}


def test_node_specificity_zero_degree_is_exactly_one():
    adj = {"a": {}}
    result = node_specificity(adj)
    # 1 / (1 + log(1 + 0)) = 1 / (1 + log(1)) = 1 / (1 + 0) = 1.0
    assert result["a"] == pytest.approx(1.0, abs=1e-12)


def test_node_specificity_degree_two_value():
    adj = {"a": {"b": 1.0, "c": 1.0}}
    result = node_specificity(adj)
    expected = 1.0 / (1.0 + math.log(1.0 + 2))
    assert result["a"] == pytest.approx(expected, rel=1e-9)


def test_node_specificity_only_includes_adj_keys_not_neighbors():
    adj = {"a": {"b": 1.0}}
    result = node_specificity(adj)
    assert set(result.keys()) == {"a"}
    assert "b" not in result


def test_node_specificity_higher_degree_yields_lower_score():
    adj = {
        "hub": {"n1": 1.0, "n2": 1.0, "n3": 1.0, "n4": 1.0},
        "leaf": {"n1": 1.0},
    }
    result = node_specificity(adj)
    assert result["hub"] < result["leaf"]


def test_node_specificity_multiple_nodes_exact_values():
    adj = {
        "a": {},
        "b": {"x": 1.0},
        "c": {"x": 1.0, "y": 1.0, "z": 1.0},
    }
    result = node_specificity(adj)
    assert result["a"] == pytest.approx(1.0, abs=1e-12)
    assert result["b"] == pytest.approx(1.0 / (1.0 + math.log(2.0)), rel=1e-9)
    assert result["c"] == pytest.approx(1.0 / (1.0 + math.log(4.0)), rel=1e-9)
