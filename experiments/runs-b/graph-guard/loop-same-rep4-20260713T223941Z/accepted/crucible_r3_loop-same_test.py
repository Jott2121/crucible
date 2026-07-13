import math
import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


def test_ppr_dangling_two_node_chain_matches_closed_form():
    # a -> b (weight 1.0); b has no outgoing edges => b is dangling.
    # Seed fully on "a". Steady state: r_a = 1/(1+alpha), r_b = alpha/(1+alpha).
    adj = {"a": {"b": 1.0}}
    alpha = 0.85
    result = personalized_pagerank(adj, ["a"], alpha=alpha, iters=200, tol=1e-12)

    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha / (1.0 + alpha)

    assert set(result.keys()) == {"a", "b"}
    assert result["a"] == pytest.approx(expected_a, rel=1e-6)
    assert result["b"] == pytest.approx(expected_b, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_zero_weight_edge_is_treated_as_dangling():
    # "a" has an outgoing edge with weight 0.0 -> its out-degree sum is 0,
    # so it must be treated exactly like a node with no outgoing edges (dangling).
    # "b" has no outgoing edges at all (also dangling).
    # Seeding entirely on "a" should push all mass back onto "a" every iteration,
    # since both nodes are perpetually dangling and the only teleport target is "a".
    adj = {"a": {"b": 0.0}, "b": {}}
    result = personalized_pagerank(adj, ["a"], alpha=0.85, iters=50, tol=1e-9)

    assert result["a"] == pytest.approx(1.0, abs=1e-9)
    assert result["b"] == pytest.approx(0.0, abs=1e-9)


def test_ppr_no_valid_seeds_falls_back_to_uniform_pagerank():
    # symmetric mutual-link graph; when personalization seeds are absent/invalid,
    # the function must fall back to uniform teleportation, giving equal ranks
    # by symmetry.
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, [], alpha=0.85, iters=100, tol=1e-12)

    assert result["a"] == pytest.approx(0.5, rel=1e-6)
    assert result["b"] == pytest.approx(0.5, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_ppr_ranks_sum_to_one_on_larger_graph():
    adj = {
        "a": {"b": 1.0, "c": 2.0},
        "b": {"c": 1.0},
        "c": {"a": 1.0},
        "d": {},  # dangling node
    }
    result = personalized_pagerank(adj, ["a", "d"], alpha=0.85, iters=100, tol=1e-12)
    assert set(result.keys()) == {"a", "b", "c", "d"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    # all ranks must be non-negative
    for v in result.values():
        assert v >= -1e-9


def test_node_specificity_exact_formula():
    adj = {
        "a": {"b": 1.0, "c": 1.0},
        "b": {"a": 1.0},
    }
    result = node_specificity(adj)

    expected_a = 1.0 / (1.0 + math.log(1.0 + 2))
    expected_b = 1.0 / (1.0 + math.log(1.0 + 1))

    assert result["a"] == pytest.approx(expected_a, rel=1e-9)
    assert result["b"] == pytest.approx(expected_b, rel=1e-9)
    # only keys present in adj should appear (c has no own row)
    assert set(result.keys()) == {"a", "b"}
