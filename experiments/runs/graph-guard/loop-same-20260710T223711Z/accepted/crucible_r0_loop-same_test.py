import math

import pytest

from graph_guard.ppr import node_specificity, personalized_pagerank


# ---------------------------------------------------------------------------
# node_specificity
# ---------------------------------------------------------------------------

def test_node_specificity_empty_adj():
    assert node_specificity({}) == {}


def test_node_specificity_zero_degree_node():
    adj = {"A": {}}
    result = node_specificity(adj)
    # degree 0 -> 1/(1+log(1)) = 1/(1+0) = 1.0
    assert result["A"] == pytest.approx(1.0, rel=1e-9)


def test_node_specificity_single_neighbor():
    adj = {"A": {"B": 1.0}}
    result = node_specificity(adj)
    expected_a = 1.0 / (1.0 + math.log(1.0 + 1))
    assert result["A"] == pytest.approx(expected_a, rel=1e-9)


def test_node_specificity_multiple_neighbors():
    adj = {"A": {"B": 1.0, "C": 2.0}}
    result = node_specificity(adj)
    expected_a = 1.0 / (1.0 + math.log(1.0 + 2))
    assert result["A"] == pytest.approx(expected_a, rel=1e-9)


def test_node_specificity_only_includes_keys_present_in_adj():
    # "B" is only referenced as a neighbor, never a key in adj -> excluded from output.
    adj = {"A": {"B": 1.0}}
    result = node_specificity(adj)
    assert set(result.keys()) == {"A"}
    assert "B" not in result


def test_node_specificity_multiple_nodes_independent_degrees():
    adj = {"A": {"B": 1.0}, "B": {}}
    result = node_specificity(adj)
    expected_a = 1.0 / (1.0 + math.log(1.0 + 1))
    expected_b = 1.0 / (1.0 + math.log(1.0 + 0))
    assert result["A"] == pytest.approx(expected_a, rel=1e-9)
    assert result["B"] == pytest.approx(expected_b, rel=1e-9)


def test_node_specificity_monotonic_decrease_with_degree():
    adj = {
        "hub": {f"n{i}": 1.0 for i in range(5)},
        "leaf": {},
    }
    result = node_specificity(adj)
    # Higher degree hub must have strictly lower specificity than the zero-degree leaf.
    assert result["hub"] < result["leaf"]
    assert result["leaf"] == pytest.approx(1.0, rel=1e-9)


# ---------------------------------------------------------------------------
# personalized_pagerank
# ---------------------------------------------------------------------------

def test_ppr_empty_adj_returns_empty_dict():
    assert personalized_pagerank({}, ["A"]) == {}


def test_ppr_single_node_no_edges_converges_to_one():
    adj = {"A": {}}
    result = personalized_pagerank(adj, ["A"])
    assert result["A"] == pytest.approx(1.0, rel=1e-6)


def test_ppr_iters_zero_returns_uniform_initial_distribution():
    adj = {"A": {}, "B": {}, "C": {}}
    result = personalized_pagerank(adj, ["A"], iters=0)
    assert result["A"] == pytest.approx(1.0 / 3.0, rel=1e-9)
    assert result["B"] == pytest.approx(1.0 / 3.0, rel=1e-9)
    assert result["C"] == pytest.approx(1.0 / 3.0, rel=1e-9)


def test_ppr_dangling_nodes_all_mass_to_seed():
    # Two isolated (dangling) nodes, personalization fully on A.
    adj = {"A": {}, "B": {}}
    result = personalized_pagerank(adj, ["A"])
    assert result["A"] == pytest.approx(1.0, rel=1e-6)
    assert result["B"] == pytest.approx(0.0, abs=1e-6)


def test_ppr_symmetric_cycle_uniform_teleport_gives_equal_scores():
    # Symmetric 2-node graph, no seeds -> falls back to uniform teleport.
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    result = personalized_pagerank(adj, [])
    assert result["A"] == pytest.approx(0.5, rel=1e-6)
    assert result["B"] == pytest.approx(0.5, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_invalid_seed_falls_back_to_all_nodes():
    # Seed not present in graph -> valid seeds becomes all nodes (uniform teleport).
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    result = personalized_pagerank(adj, ["not_a_node"])
    assert result["A"] == pytest.approx(0.5, rel=1e-6)
    assert result["B"] == pytest.approx(0.5, rel=1e-6)


def test_ppr_directed_chain_with_dangling_sink_analytic_fixed_point():
    # A -> B (weight 1), B has no outgoing edges (dangling). Seed on A only.
    adj = {"A": {"B": 1.0}}
    alpha = 0.85
    result = personalized_pagerank(adj, ["A"], alpha=alpha)

    # Analytic fixed point:
    # rank_A = (1 - alpha) + alpha * rank_B
    # rank_B = alpha * rank_A
    # => rank_A = (1 - alpha) / (1 - alpha**2) = 1 / (1 + alpha)
    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha * expected_a

    assert result["A"] == pytest.approx(expected_a, abs=1e-3)
    assert result["B"] == pytest.approx(expected_b, abs=1e-3)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    # Seeded node should retain higher rank than the pure sink in this configuration.
    assert result["A"] > result["B"]


def test_ppr_scores_sum_to_approximately_one_general_graph():
    adj = {
        "A": {"B": 1.0, "C": 3.0},
        "B": {"C": 1.0},
        "C": {"A": 2.0},
        "D": {},  # dangling node
    }
    result = personalized_pagerank(adj, ["A", "D"])
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    assert set(result.keys()) == {"A", "B", "C", "D"}
    for v in result.values():
        assert v >= 0.0


def test_ppr_all_nodes_present_even_when_only_referenced_as_neighbor():
    adj = {"A": {"B": 1.0}}
    result = personalized_pagerank(adj, ["A"])
    assert set(result.keys()) == {"A", "B"}
