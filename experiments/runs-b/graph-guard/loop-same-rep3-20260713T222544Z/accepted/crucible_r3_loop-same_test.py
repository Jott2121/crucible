import math
import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


def test_dangling_node_single_iteration_exact():
    """Node B has no outgoing edges (absent from adj entirely) and A points to B.
    With iters=1 we can hand-compute the exact PPR update, exercising both the
    `out_sum.get(u, ...)` dangling check and the `adj.get(u, ...)` neighbor lookup."""
    adj = {"A": {"B": 1.0}}
    result = personalized_pagerank(adj, ["A"], alpha=0.85, iters=1, tol=0.0)

    alpha = 0.85
    rank0 = 0.5  # uniform initial rank over {A, B}
    # A -> B contributes alpha * rank0 * (1.0/1.0) to B
    expected_b = alpha * rank0 * 1.0
    # B is dangling: all of its rank mass is redistributed via teleport to A
    dangling_mass = rank0
    mass = (1.0 - alpha) + alpha * dangling_mass
    expected_a = mass * 1.0  # all teleport probability is on A

    assert result["B"] == pytest.approx(expected_b, rel=1e-9)
    assert result["A"] == pytest.approx(expected_a, rel=1e-9)
    assert result["A"] + result["B"] == pytest.approx(1.0, rel=1e-9)


def test_dangling_node_explicit_empty_dict_matches_absent_key():
    """A node explicitly present as a key with an empty neighbor dict must behave
    identically to a node that is only referenced as a neighbor (absent key)."""
    adj_absent = {"A": {"B": 1.0}}
    adj_explicit = {"A": {"B": 1.0}, "B": {}}

    result_absent = personalized_pagerank(adj_absent, ["A"], alpha=0.85, iters=1, tol=0.0)
    result_explicit = personalized_pagerank(adj_explicit, ["A"], alpha=0.85, iters=1, tol=0.0)

    assert result_absent["A"] == pytest.approx(result_explicit["A"], rel=1e-9)
    assert result_absent["B"] == pytest.approx(result_explicit["B"], rel=1e-9)


def test_multiple_dangling_nodes_sum_to_one_and_seed_favored():
    """Two seedless dangling nodes and one seeded hub; after convergence the total
    rank mass must still sum to ~1, and the seeded node must retain the most rank
    since all dangling mass and teleport mass funnels back to it."""
    adj = {
        "seed": {"d1": 1.0, "d2": 1.0},
        # d1, d2 have no outgoing edges -> dangling
    }
    result = personalized_pagerank(adj, ["seed"], alpha=0.85, iters=50, tol=1e-12)

    total = sum(result.values())
    assert total == pytest.approx(1.0, rel=1e-6)
    assert result["seed"] > result["d1"]
    assert result["seed"] > result["d2"]
    assert result["d1"] == pytest.approx(result["d2"], rel=1e-6)


def test_weighted_dangling_redistribution_ratio():
    """A dangling node's incoming rank should split proportionally to edge weight,
    and after a single iteration the two receiving nodes' ratio matches the weight ratio."""
    adj = {"seed": {"x": 3.0, "y": 1.0}}
    result = personalized_pagerank(adj, ["seed"], alpha=0.85, iters=1, tol=0.0)

    # both x and y are dangling; their first-iteration mass is alpha * 0.5 * (w / total_w)
    total_w = 4.0
    rank0 = 1.0 / 3.0  # three nodes total: seed, x, y
    expected_x = 0.85 * rank0 * (3.0 / total_w)
    expected_y = 0.85 * rank0 * (1.0 / total_w)

    assert result["x"] == pytest.approx(expected_x, rel=1e-9)
    assert result["y"] == pytest.approx(expected_y, rel=1e-9)
    assert result["x"] / result["y"] == pytest.approx(3.0, rel=1e-6)
