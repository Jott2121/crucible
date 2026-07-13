import math

import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


# ---------------------------------------------------------------------------
# personalized_pagerank
# ---------------------------------------------------------------------------

def test_ppr_empty_graph_returns_empty_dict():
    assert personalized_pagerank({}, []) == {}


def test_ppr_single_isolated_node_seeded_gets_full_mass():
    adj = {"A": {}}
    result = personalized_pagerank(adj, ["A"])
    assert set(result.keys()) == {"A"}
    assert result["A"] == pytest.approx(1.0, abs=1e-6)


def test_ppr_two_isolated_nodes_all_mass_funnels_to_seed():
    # Both nodes are dangling (no out-edges); all probability mass must
    # eventually funnel through the teleport vector onto the seed node.
    adj = {"A": {}, "B": {}}
    result = personalized_pagerank(adj, ["A"])
    assert result["A"] == pytest.approx(1.0, abs=1e-6)
    assert result["B"] == pytest.approx(0.0, abs=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_invalid_seeds_fallback_to_uniform_teleport_over_all_nodes():
    # Seed not present in the graph -> falls back to teleporting over all
    # nodes, same as the "no seeds" behaviour for a single dangling node.
    adj = {"A": {}}
    result = personalized_pagerank(adj, ["not_in_graph"])
    assert result["A"] == pytest.approx(1.0, abs=1e-6)


def test_ppr_symmetric_two_node_graph_uniform_teleport_is_symmetric():
    # Symmetric ring of 2 equally-weighted nodes with uniform teleport
    # (no valid seeds) must converge to a uniform 0.5/0.5 split.
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    result = personalized_pagerank(adj, [])
    assert result["A"] == pytest.approx(0.5, rel=1e-6)
    assert result["B"] == pytest.approx(0.5, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_alpha_zero_collapses_to_pure_teleport_distribution():
    # With alpha=0 the random-walk term vanishes entirely; the stationary
    # distribution must equal the teleport (personalization) vector.
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    result = personalized_pagerank(adj, ["A"], alpha=0.0)
    assert result["A"] == pytest.approx(1.0, abs=1e-6)
    assert result["B"] == pytest.approx(0.0, abs=1e-6)


def test_ppr_scores_sum_to_one_for_multi_node_graph():
    adj = {
        "A": {"B": 1.0, "C": 2.0},
        "B": {"C": 1.0},
        "C": {"A": 0.5},
        "D": {},
    }
    result = personalized_pagerank(adj, ["A", "D"])
    assert set(result.keys()) == {"A", "B", "C", "D"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    # all scores must be non-negative probabilities
    for v in result.values():
        assert v >= -1e-9


def test_ppr_includes_neighbor_only_nodes_not_present_as_keys():
    # 'B' only appears as a neighbor, never as a top-level key in adj.
    adj = {"A": {"B": 1.0}}
    result = personalized_pagerank(adj, ["A"])
    assert set(result.keys()) == {"A", "B"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# node_specificity
# ---------------------------------------------------------------------------

def test_node_specificity_empty_dict():
    assert node_specificity({}) == {}


def test_node_specificity_zero_degree_node_scores_one():
    adj = {"A": {}}
    result = node_specificity(adj)
    assert result["A"] == pytest.approx(1.0, rel=1e-9)


def test_node_specificity_matches_formula_for_various_degrees():
    adj = {
        "A": {"B": 1.0, "C": 1.0},  # degree 2
        "B": {},                    # degree 0
        "C": {"A": 3.5},            # degree 1
    }
    result = node_specificity(adj)

    expected_a = 1.0 / (1.0 + math.log(1.0 + 2))
    expected_b = 1.0 / (1.0 + math.log(1.0 + 0))
    expected_c = 1.0 / (1.0 + math.log(1.0 + 1))

    assert result["A"] == pytest.approx(expected_a, rel=1e-9)
    assert result["B"] == pytest.approx(expected_b, rel=1e-9)
    assert result["C"] == pytest.approx(expected_c, rel=1e-9)


def test_node_specificity_higher_degree_yields_lower_score():
    adj = {
        "hub": {"n1": 1.0, "n2": 1.0, "n3": 1.0, "n4": 1.0},
        "leaf": {"n1": 1.0},
    }
    result = node_specificity(adj)
    assert result["hub"] < result["leaf"]
    assert result["leaf"] == pytest.approx(1.0 / (1.0 + math.log(2.0)), rel=1e-9)


def test_node_specificity_ignores_neighbor_only_nodes():
    # Only keys of adj get a specificity score; pure neighbors are absent.
    adj = {"A": {"B": 1.0}}
    result = node_specificity(adj)
    assert set(result.keys()) == {"A"}
    assert "B" not in result

