import math
import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


def test_ppr_two_node_stationary_distribution():
    # a -> b (weight 1), b is a dangling node (no outgoing edges).
    # Seed personalization entirely on 'a'.
    adj = {"a": {"b": 1.0}, "b": {}}
    alpha = 0.85

    # Closed form for this simple system (derived by hand):
    #   ra = (1 - alpha) + alpha * rb        (rb is the only dangling mass)
    #   rb = alpha * ra
    # => ra = 1 / (1 + alpha),  rb = alpha / (1 + alpha)
    expected_ra = 1.0 / (1.0 + alpha)
    expected_rb = alpha / (1.0 + alpha)

    result = personalized_pagerank(adj, ["a"], alpha=alpha, iters=2000, tol=1e-15)

    assert result["a"] == pytest.approx(expected_ra, rel=1e-6)
    assert result["b"] == pytest.approx(expected_rb, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_fully_dangling_graph_puts_all_mass_on_seed():
    # No edges at all: both nodes are dangling. All rank mass must funnel
    # through the teleport vector onto the seed node every iteration.
    adj = {"a": {}, "b": {}}
    result = personalized_pagerank(adj, ["a"], alpha=0.85, iters=10, tol=1e-15)

    assert result["a"] == pytest.approx(1.0, rel=1e-6)
    assert result["b"] == pytest.approx(0.0, abs=1e-6)


def test_ppr_sums_to_one_with_mixed_dangling_nodes():
    # Mixed graph: one node has outgoing edges, one is dangling, one is isolated.
    adj = {
        "a": {"b": 2.0, "c": 1.0},
        "b": {},
        "c": {"a": 1.0},
    }
    result = personalized_pagerank(adj, ["a", "c"], alpha=0.85, iters=200, tol=1e-12)

    assert set(result) == {"a", "b", "c"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    # All scores must remain non-negative probabilities.
    for score in result.values():
        assert score >= -1e-9


def test_ppr_fallback_to_uniform_teleport_on_symmetric_cycle():
    # When none of the requested seeds exist among the graph nodes, the
    # implementation falls back to teleporting uniformly over all nodes.
    # On a perfectly symmetric 3-node cycle with equal weights, this must
    # yield (approximately) equal scores for every node.
    adj = {
        "a": {"b": 1.0},
        "b": {"c": 1.0},
        "c": {"a": 1.0},
    }
    result = personalized_pagerank(adj, ["not_in_graph"], alpha=0.85, iters=500, tol=1e-13)

    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    for node in ("a", "b", "c"):
        assert result[node] == pytest.approx(1.0 / 3.0, rel=1e-5)


def test_ppr_explicit_empty_neighbor_dict_matches_absent_key():
    # A node listed explicitly with an empty neighbor dict must behave
    # identically to a node that is only ever referenced as a neighbor
    # (i.e. never appears as a top-level key in `adj`).
    adj_explicit = {"a": {"b": 1.0}, "b": {}}
    adj_implicit = {"a": {"b": 1.0}}

    r_explicit = personalized_pagerank(adj_explicit, ["a"], alpha=0.85, iters=500, tol=1e-13)
    r_implicit = personalized_pagerank(adj_implicit, ["a"], alpha=0.85, iters=500, tol=1e-13)

    assert set(r_explicit) == set(r_implicit) == {"a", "b"}
    assert r_explicit["a"] == pytest.approx(r_implicit["a"], rel=1e-9)
    assert r_explicit["b"] == pytest.approx(r_implicit["b"], rel=1e-9)


def test_node_specificity_exact_formula():
    adj = {
        "isolated": {},
        "hub": {"n1": 1.0, "n2": 1.0},
    }
    result = node_specificity(adj)

    expected_isolated = 1.0 / (1.0 + math.log(1.0 + 0))
    expected_hub = 1.0 / (1.0 + math.log(1.0 + 2))

    assert result["isolated"] == pytest.approx(expected_isolated, rel=1e-9)
    assert result["hub"] == pytest.approx(expected_hub, rel=1e-9)
    # Higher-degree hub nodes must be down-weighted relative to isolated ones.
    assert result["hub"] < result["isolated"]
