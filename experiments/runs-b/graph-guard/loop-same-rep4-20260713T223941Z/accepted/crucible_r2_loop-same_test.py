import math
import pytest

from graph_guard.ppr import personalized_pagerank


def test_dangling_node_redistribution_analytic():
    # A -> B (weight 1), B has no outgoing edges (dangling).
    # Seed on A only. Analytic fixed point:
    # a = 1/(1+alpha), b = alpha/(1+alpha)  with alpha=0.85
    adj = {"A": {"B": 1.0}, "B": {}}
    alpha = 0.85
    rank = personalized_pagerank(adj, ["A"], alpha=alpha, iters=200, tol=1e-12)

    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha / (1.0 + alpha)

    assert rank["A"] == pytest.approx(expected_a, rel=1e-6)
    assert rank["B"] == pytest.approx(expected_b, rel=1e-6)
    assert sum(rank.values()) == pytest.approx(1.0, rel=1e-6)


def test_two_fully_dangling_nodes_single_seed():
    # No edges at all; both nodes are dangling. Seed on "A" only.
    # Because both nodes are dangling, all rank mass is dangling mass each
    # iteration, so the teleport vector (100% on A) is the exact fixed point.
    adj = {"A": {}, "B": {}}
    rank = personalized_pagerank(adj, ["A"], alpha=0.85, iters=50, tol=1e-9)

    assert rank["A"] == pytest.approx(1.0, rel=1e-6)
    assert rank["B"] == pytest.approx(0.0, abs=1e-6)
    assert sum(rank.values()) == pytest.approx(1.0, rel=1e-6)


def test_two_fully_dangling_nodes_two_seeds_uniform():
    # No edges; both nodes dangling; seeds split evenly between A and B.
    # Fixed point should equal the teleport vector: 0.5 / 0.5.
    adj = {"A": {}, "B": {}}
    rank = personalized_pagerank(adj, ["A", "B"], alpha=0.85, iters=50, tol=1e-9)

    assert rank["A"] == pytest.approx(0.5, rel=1e-6)
    assert rank["B"] == pytest.approx(0.5, rel=1e-6)
    assert sum(rank.values()) == pytest.approx(1.0, rel=1e-6)


def test_dangling_node_not_present_as_adj_key():
    # C only appears as a neighbor target and is never a key in adj itself.
    # A -> B -> C ; C has no outgoing edges (implicit dangling, absent key).
    adj = {"A": {"B": 1.0}, "B": {"C": 1.0}}
    alpha = 0.85
    rank = personalized_pagerank(adj, ["A"], alpha=alpha, iters=500, tol=1e-12)

    # All rank mass must still sum to 1, and C (a pure sink) must accumulate
    # a positive, finite share of rank since PPR redistributes dangling mass
    # via teleportation back through the graph.
    total = sum(rank.values())
    assert total == pytest.approx(1.0, rel=1e-6)
    assert rank["C"] > 0.0
    assert rank["A"] > 0.0
    assert rank["B"] > 0.0

    # A should retain the largest share since it's the sole seed and closest
    # to the teleport source across iterations converging to a stationary dist.
    assert rank["A"] >= rank["B"]
    assert rank["A"] >= rank["C"]


def test_mixed_dangling_and_normal_nodes_sum_to_one():
    # Mixture: D is dangling, A/B/C form a small cycle-ish structure.
    adj = {
        "A": {"B": 1.0},
        "B": {"C": 1.0},
        "C": {"A": 0.5, "D": 0.5},
        "D": {},
    }
    rank = personalized_pagerank(adj, ["A"], alpha=0.85, iters=200, tol=1e-12)
    total = sum(rank.values())
    assert total == pytest.approx(1.0, rel=1e-6)
    # every node reachable should have positive rank
    for node in ["A", "B", "C", "D"]:
        assert rank[node] > 0.0
