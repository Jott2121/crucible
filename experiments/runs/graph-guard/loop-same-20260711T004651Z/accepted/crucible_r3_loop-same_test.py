import math
import pytest

from graph_guard.ppr import personalized_pagerank


def test_ppr_two_node_symmetric_exact_values():
    # Simple symmetric 2-cycle: a <-> b, both weight 1, seeded on 'a'.
    # Fixed point solves: a = alpha*b + (1-alpha), b = alpha*a, a+b=1
    # => a = 1/(1+alpha), b = alpha/(1+alpha)
    alpha = 0.85
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, ["a"], alpha=alpha)

    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha / (1.0 + alpha)

    assert result["a"] == pytest.approx(expected_a, abs=1e-4)
    assert result["b"] == pytest.approx(expected_b, abs=1e-4)
    # Mass conservation is exact arithmetic invariant of the update rule.
    assert sum(result.values()) == pytest.approx(1.0, abs=1e-9)


def test_ppr_dangling_node_handling():
    # a -> b (weight 1), b has NO outgoing edges (dangling).
    # This exercises the exact branch where `s <= 0` continues and
    # dangling mass is redistributed via the teleport vector.
    alpha = 0.85
    adj = {"a": {"b": 1.0}}
    result = personalized_pagerank(adj, ["a"], alpha=alpha)

    # By analysis: a_{t+1} = (1-alpha) + alpha*b_t, b_{t+1} = alpha*a_t
    # Fixed point: a = 1/(1+alpha), b = alpha/(1+alpha)  (same algebra as above)
    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha / (1.0 + alpha)

    assert result["a"] == pytest.approx(expected_a, abs=1e-4)
    assert result["b"] == pytest.approx(expected_b, abs=1e-4)
    # Total probability mass must still sum to ~1 even with a dangling node.
    assert sum(result.values()) == pytest.approx(1.0, abs=1e-9)


def test_ppr_absent_seeds_falls_back_to_uniform_teleport():
    # Fully symmetric 2-node graph; if no seed is valid, the code falls back
    # to uniform teleportation over all nodes. By symmetry the stationary
    # distribution must be exactly uniform (0.5, 0.5).
    adj = {"x": {"y": 1.0}, "y": {"x": 1.0}}
    result = personalized_pagerank(adj, ["node_not_in_graph"])

    assert result["x"] == pytest.approx(0.5, abs=1e-9)
    assert result["y"] == pytest.approx(0.5, abs=1e-9)
    assert sum(result.values()) == pytest.approx(1.0, abs=1e-9)


def test_ppr_dangling_node_no_crash_and_valid_scores():
    # Regression/robustness check: a node with an empty adjacency and one
    # with only negative-net edges should not crash, and results must remain
    # valid probabilities summing to ~1.
    adj = {"a": {"b": 1.0}, "b": {}}
    result = personalized_pagerank(adj, ["a"])
    assert set(result) == {"a", "b"}
    for v in result.values():
        assert v >= 0.0
    assert sum(result.values()) == pytest.approx(1.0, abs=1e-9)
