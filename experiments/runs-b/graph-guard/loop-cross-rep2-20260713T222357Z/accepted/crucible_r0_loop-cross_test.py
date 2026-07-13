import math
import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


# ---------------------------------------------------------------------------
# personalized_pagerank
# ---------------------------------------------------------------------------

def test_ppr_empty_adj_returns_empty_dict():
    assert personalized_pagerank({}, seeds=["x"]) == {}


def test_ppr_single_node_no_edges_converges_to_one():
    adj = {"a": {}}
    result = personalized_pagerank(adj, seeds=["a"])
    assert set(result.keys()) == {"a"}
    assert result["a"] == pytest.approx(1.0, rel=1e-9)


def test_ppr_iters_zero_returns_uniform_distribution():
    # With iters=0 the update loop never runs, so rank stays at the
    # initial uniform value 1/n regardless of seeds/edges.
    adj = {"a": {"b": 1.0}, "b": {}}
    result = personalized_pagerank(adj, seeds=["a"], iters=0)
    assert result["a"] == pytest.approx(0.5, rel=1e-9)
    assert result["b"] == pytest.approx(0.5, rel=1e-9)


def test_ppr_two_node_chain_matches_closed_form():
    # a -> b (weight 1), b has no outgoing edges (dangling).
    # Seed is 'a'. Steady state solves:
    #   ra = (1-alpha) + alpha*rb
    #   rb = alpha*ra
    # => ra = 1/(1+alpha), rb = alpha/(1+alpha)
    alpha = 0.85
    adj = {"a": {"b": 1.0}, "b": {}}
    result = personalized_pagerank(adj, seeds=["a"], alpha=alpha, iters=200, tol=1e-12)

    expected_ra = 1.0 / (1.0 + alpha)
    expected_rb = alpha / (1.0 + alpha)

    assert result["a"] == pytest.approx(expected_ra, rel=1e-6)
    assert result["b"] == pytest.approx(expected_rb, rel=1e-6)
    assert (result["a"] + result["b"]) == pytest.approx(1.0, rel=1e-6)


def test_ppr_symmetric_graph_with_invalid_seed_falls_back_to_uniform_teleport():
    # No valid seeds present in the graph -> uniform teleport over all
    # nodes (plain PageRank). Symmetric mutual edges => equal scores.
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, seeds=["not_in_graph"], iters=200, tol=1e-12)
    assert result["a"] == pytest.approx(0.5, rel=1e-6)
    assert result["b"] == pytest.approx(0.5, rel=1e-6)


def test_ppr_empty_seeds_falls_back_to_uniform_teleport():
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, seeds=[], iters=200, tol=1e-12)
    assert result["a"] == pytest.approx(0.5, rel=1e-6)
    assert result["b"] == pytest.approx(0.5, rel=1e-6)


def test_ppr_sums_to_one_on_three_node_cycle():
    adj = {
        "a": {"b": 1.0},
        "b": {"c": 1.0},
        "c": {"a": 1.0},
    }
    result = personalized_pagerank(adj, seeds=["a"])
    total = sum(result.values())
    assert total == pytest.approx(1.0, rel=1e-6)
    # all three nodes must appear in output
    assert set(result.keys()) == {"a", "b", "c"}


def test_ppr_seeded_node_scores_higher_than_unreachable_isolated_node():
    # 'c' is isolated (no edges at all, in or out) so it can only receive
    # mass via teleport; since it's not a seed it should score lower than
    # the seed node 'a' which receives direct teleport mass.
    adj = {"a": {"b": 1.0}, "b": {}, "c": {}}
    result = personalized_pagerank(adj, seeds=["a"], iters=200, tol=1e-12)
    assert result["a"] > result["c"]


def test_ppr_nodes_only_appearing_as_neighbors_are_included():
    adj = {"a": {"b": 2.0, "c": 1.0}}
    result = personalized_pagerank(adj, seeds=["a"])
    assert set(result.keys()) == {"a", "b", "c"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# node_specificity
# ---------------------------------------------------------------------------

def test_node_specificity_empty_adj():
    assert node_specificity({}) == {}


def test_node_specificity_zero_degree_is_one():
    adj = {"a": {}}
    result = node_specificity(adj)
    assert result["a"] == pytest.approx(1.0, rel=1e-9)


def test_node_specificity_formula_for_degree_two():
    adj = {"b": {"a": 1.0, "c": 1.0}}
    result = node_specificity(adj)
    expected = 1.0 / (1.0 + math.log(1.0 + 2))
    assert result["b"] == pytest.approx(expected, rel=1e-9)


def test_node_specificity_hub_scores_lower_than_leaf():
    adj = {
        "hub": {"n1": 1.0, "n2": 1.0, "n3": 1.0, "n4": 1.0},
        "n1": {},
        "n2": {},
        "n3": {},
        "n4": {},
    }
    result = node_specificity(adj)
    expected_hub = 1.0 / (1.0 + math.log(1.0 + 4))
    assert result["hub"] == pytest.approx(expected_hub, rel=1e-9)
    assert result["n1"] == pytest.approx(1.0, rel=1e-9)
    assert result["hub"] < result["n1"]


def test_node_specificity_only_iterates_over_adj_keys():
    # node_specificity only computes for keys in adj (not neighbor-only
    # nodes), per the docstring's reliance on symmetric adjacency rows.
    adj = {"x": {"y": 1.0}}
    result = node_specificity(adj)
    assert set(result.keys()) == {"x"}

