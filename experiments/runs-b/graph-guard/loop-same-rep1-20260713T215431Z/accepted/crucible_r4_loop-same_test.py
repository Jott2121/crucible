import math
import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


def test_dangling_node_closed_form_values():
    # A -> B (weight 1), B has no outgoing edges at all (not even a key in adj),
    # so B is a "dangling" node whose rank mass must be redistributed via the
    # teleport vector (seeded entirely on A).
    adj = {"A": {"B": 1.0}}
    alpha = 0.85
    result = personalized_pagerank(adj, seeds=["A"], alpha=alpha, iters=200, tol=1e-12)

    # Closed form for this 2-node dangling chain with teleport fully on A:
    #   a = 1 / (1 + alpha)
    #   b = alpha * a
    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha * expected_a

    assert set(result) == {"A", "B"}
    assert result["A"] == pytest.approx(expected_a, rel=1e-6)
    assert result["B"] == pytest.approx(expected_b, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_dangling_node_present_as_empty_dict_key():
    # Same scenario, but B explicitly present in adj with an empty neighbor dict.
    # Must behave identically to B being absent entirely.
    adj = {"A": {"B": 1.0}, "B": {}}
    alpha = 0.85
    result = personalized_pagerank(adj, seeds=["A"], alpha=alpha, iters=200, tol=1e-12)

    expected_a = 1.0 / (1.0 + alpha)
    expected_b = alpha * expected_a

    assert result["A"] == pytest.approx(expected_a, rel=1e-6)
    assert result["B"] == pytest.approx(expected_b, rel=1e-6)


def test_multiple_dangling_nodes_redistribute_correctly():
    # Two dangling nodes, both receiving equal edge weight from a hub node.
    # Seed personalization only on the hub node "H".
    adj = {"H": {"D1": 1.0, "D2": 1.0}}
    alpha = 0.85
    result = personalized_pagerank(adj, seeds=["H"], alpha=alpha, iters=300, tol=1e-12)

    # By symmetry D1 and D2 must have equal rank.
    assert result["D1"] == pytest.approx(result["D2"], rel=1e-6)

    # Closed form: h = fraction on hub, d = fraction on each dangling node.
    # h + 2d = 1
    # h receives: (1-alpha) + alpha*(2d)  [dangling mass fully returns via teleport]
    # d receives: alpha*h/2  (H splits its rank equally over D1, D2)
    # Solve: d = alpha*h/2  =>  h = (1-alpha) + alpha*(2*(alpha*h/2)) = (1-alpha) + alpha^2*h
    # h*(1-alpha^2) = 1-alpha  =>  h = 1/(1+alpha)
    expected_h = 1.0 / (1.0 + alpha)
    expected_d = alpha * expected_h / 2.0

    assert result["H"] == pytest.approx(expected_h, rel=1e-6)
    assert result["D1"] == pytest.approx(expected_d, rel=1e-6)
    assert result["D2"] == pytest.approx(expected_d, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_pagerank_sums_to_one_with_mixed_dangling_and_normal_nodes():
    adj = {
        "A": {"B": 2.0, "C": 1.0},
        "B": {"C": 1.0},
        # "C" is dangling: never a key in adj
    }
    result = personalized_pagerank(adj, seeds=["A"], alpha=0.85, iters=200, tol=1e-12)
    assert set(result) == {"A", "B", "C"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    # All scores must be non-negative and finite.
    for v in result.values():
        assert v >= 0.0
        assert math.isfinite(v)
