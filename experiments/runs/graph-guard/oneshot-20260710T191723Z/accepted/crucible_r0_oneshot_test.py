import math
import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


# ---------------------------------------------------------------------------
# personalized_pagerank
# ---------------------------------------------------------------------------

def test_ppr_empty_graph_returns_empty_dict():
    assert personalized_pagerank({}, []) == {}


def test_ppr_single_node_no_edges_all_dangling_converges_to_one():
    adj = {"A": {}}
    result = personalized_pagerank(adj, ["A"])
    assert set(result.keys()) == {"A"}
    assert result["A"] == pytest.approx(1.0, abs=1e-9)


def test_ppr_two_node_cycle_absent_seed_falls_back_to_uniform_symmetric():
    # Seed not present in the graph -> falls back to uniform teleport over
    # all nodes. Graph is a symmetric 2-cycle, so by symmetry both nodes
    # should end up with equal, exact score of 0.5 each.
    adj = {"X": {"Y": 1.0}, "Y": {"X": 1.0}}
    result = personalized_pagerank(adj, ["Z"])
    assert result["X"] == pytest.approx(0.5, abs=1e-9)
    assert result["Y"] == pytest.approx(0.5, abs=1e-9)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-9)


def test_ppr_two_node_cycle_seed_asymmetric_converges_near_fixed_point():
    # adj = symmetric 2-cycle, seed only on 'A'. Fixed point of the linear
    # recurrence a = alpha*(1-a) + (1-alpha) with alpha=0.85 gives
    # a* = 1/(1+alpha) = 1/1.85 ~= 0.540540541, b* = alpha/(1+alpha) ~= 0.459459459.
    # After 50 iterations the sequence has nearly converged to this fixed point.
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    result = personalized_pagerank(adj, ["A"], alpha=0.85, iters=50, tol=1e-9)
    assert result["A"] == pytest.approx(0.540540541, abs=1e-3)
    assert result["B"] == pytest.approx(0.459459459, abs=1e-3)
    assert result["A"] > result["B"]
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_all_dangling_nodes_mass_goes_to_seed():
    # No outgoing edges anywhere -> every node dangles each iteration and
    # the full probability mass is teleported to the seed each round.
    adj = {"A": {}, "B": {}}
    result = personalized_pagerank(adj, ["A"])
    assert result["A"] == pytest.approx(1.0, abs=1e-9)
    assert result["B"] == pytest.approx(0.0, abs=1e-9)


def test_ppr_alpha_zero_equals_pure_personalization_vector():
    # With alpha=0, no probability flows across edges; the result converges
    # exactly to the teleport (personalization) distribution.
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    result = personalized_pagerank(adj, ["A"], alpha=0.0)
    assert result["A"] == pytest.approx(1.0, abs=1e-12)
    assert result["B"] == pytest.approx(0.0, abs=1e-12)


def test_ppr_scores_sum_to_one_on_three_node_graph():
    adj = {
        "A": {"B": 1.0, "C": 2.0},
        "B": {"C": 1.0},
        "C": {"A": 1.0},
    }
    result = personalized_pagerank(adj, ["A"])
    assert set(result.keys()) == {"A", "B", "C"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    assert all(v >= 0.0 for v in result.values())


def test_ppr_includes_nodes_only_appearing_as_neighbors():
    # 'D' never appears as a key in adj, only as a neighbor value; it must
    # still be included in the resulting node set.
    adj = {"A": {"D": 1.0}}
    result = personalized_pagerank(adj, ["A"])
    assert set(result.keys()) == {"A", "D"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# node_specificity
# ---------------------------------------------------------------------------

def test_node_specificity_empty_adj_returns_empty_dict():
    assert node_specificity({}) == {}


def test_node_specificity_zero_degree_node_equals_one():
    adj = {"a": {}}
    result = node_specificity(adj)
    expected = 1.0 / (1.0 + math.log(1.0 + 0))
    assert result["a"] == pytest.approx(expected, rel=1e-9)
    assert result["a"] == pytest.approx(1.0, rel=1e-9)


def test_node_specificity_exact_formula_for_degree_two():
    adj = {"a": {"b": 1.0, "c": 2.0}}
    expected = 1.0 / (1.0 + math.log(1.0 + 2))
    result = node_specificity(adj)
    assert result["a"] == pytest.approx(expected, rel=1e-9)


def test_node_specificity_exact_formula_for_degree_five():
    adj = {"hub": {str(i): 1.0 for i in range(5)}}
    expected = 1.0 / (1.0 + math.log(1.0 + 5))
    result = node_specificity(adj)
    assert result["hub"] == pytest.approx(expected, rel=1e-9)


def test_node_specificity_higher_degree_yields_lower_score():
    adj = {
        "low": {"x": 1.0},
        "high": {"x": 1.0, "y": 1.0, "z": 1.0, "w": 1.0},
    }
    result = node_specificity(adj)
    assert result["low"] > result["high"]


def test_node_specificity_multiple_keys_independent_computation():
    adj = {
        "n1": {},
        "n2": {"a": 1.0},
        "n3": {"a": 1.0, "b": 1.0},
    }
    result = node_specificity(adj)
    expected_n1 = 1.0 / (1.0 + math.log(1.0 + 0))
    expected_n2 = 1.0 / (1.0 + math.log(1.0 + 1))
    expected_n3 = 1.0 / (1.0 + math.log(1.0 + 2))
    assert result["n1"] == pytest.approx(expected_n1, rel=1e-9)
    assert result["n2"] == pytest.approx(expected_n2, rel=1e-9)
    assert result["n3"] == pytest.approx(expected_n3, rel=1e-9)
