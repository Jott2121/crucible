import math

import pytest

from graph_guard.ppr import personalized_pagerank, node_specificity


# ---------------------------------------------------------------------------
# personalized_pagerank
# ---------------------------------------------------------------------------

def test_empty_adj_returns_empty_dict():
    assert personalized_pagerank({}, []) == {}


def test_single_node_no_edges_exact():
    # Single dangling node seeded on itself: all mass returns to it immediately.
    adj = {"A": {}}
    result = personalized_pagerank(adj, ["A"])
    assert set(result.keys()) == {"A"}
    assert result["A"] == pytest.approx(1.0, abs=1e-9)


def test_two_node_symmetric_seed_missing_falls_back_uniform_exact():
    # Seed "Z" is not a node, so teleport falls back to uniform over all nodes.
    # By symmetry of the graph and uniform teleport/init, the fixed point is
    # reached immediately at 0.5/0.5 and stays there (delta == 0).
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    result = personalized_pagerank(adj, ["Z"])
    assert set(result.keys()) == {"A", "B"}
    assert result["A"] == pytest.approx(0.5, abs=1e-9)
    assert result["B"] == pytest.approx(0.5, abs=1e-9)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-9)


def test_two_node_directed_cycle_biased_toward_seed():
    # A <-> B cycle, seeded only on A. Recurrence x_{t+1} = 1 - alpha*x_t
    # converges to x* = 1/(1+alpha) = 1/1.85 ~ 0.540540541 for A,
    # and 1 - x* ~ 0.459459459 for B. With alpha=0.85 and 50 iterations,
    # the error is on the order of 1e-5.
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    result = personalized_pagerank(adj, ["A"])
    assert result["A"] == pytest.approx(0.540540541, abs=1e-3)
    assert result["B"] == pytest.approx(0.459459459, abs=1e-3)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_dangling_node_same_asymptotic_ratio():
    # A -> B with B dangling (no outgoing edges). All rank leaving B via the
    # dangling redistribution returns entirely to the seed A, giving the same
    # recurrence x_{t+1} = 1 - alpha*x_t as the two-node cycle case.
    adj = {"A": {"B": 2.0}}
    result = personalized_pagerank(adj, ["A"])
    assert set(result.keys()) == {"A", "B"}
    assert result["A"] == pytest.approx(0.540540541, abs=1e-3)
    assert result["B"] == pytest.approx(0.459459459, abs=1e-3)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_partial_valid_seeds_ignores_invalid_entries():
    # "Z" is not a graph node and should simply be filtered out, leaving only
    # "A" as an effective seed -- same result as seeding on "A" alone.
    adj = {"A": {"B": 2.0}}
    result = personalized_pagerank(adj, ["A", "Z"])
    assert result["A"] == pytest.approx(0.540540541, abs=1e-3)
    assert result["B"] == pytest.approx(0.459459459, abs=1e-3)


def test_sum_of_scores_is_one_for_larger_graph():
    adj = {
        "A": {"B": 1.0, "C": 1.0},
        "B": {"C": 1.0},
        "C": {"A": 1.0},
    }
    result = personalized_pagerank(adj, ["A"])
    assert set(result.keys()) == {"A", "B", "C"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_all_scores_are_nonnegative():
    adj = {
        "A": {"B": 1.0, "C": 1.0},
        "B": {"C": 1.0},
        "C": {"A": 1.0},
        "D": {},  # isolated dangling node
    }
    result = personalized_pagerank(adj, ["A"])
    for v in result.values():
        assert v >= 0.0


def test_isolated_node_included_and_total_still_one():
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}, "D": {}}
    result = personalized_pagerank(adj, ["A"])
    assert set(result.keys()) == {"A", "B", "D"}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# node_specificity
# ---------------------------------------------------------------------------

def test_node_specificity_empty_adj():
    assert node_specificity({}) == {}


def test_node_specificity_degree_zero():
    adj = {"A": {}}
    expected = 1.0 / (1.0 + math.log(1.0 + 0))
    result = node_specificity(adj)
    assert result["A"] == pytest.approx(expected, rel=1e-9)
    assert result["A"] == pytest.approx(1.0, rel=1e-9)


def test_node_specificity_degree_one():
    adj = {"A": {"B": 1.0}}
    expected = 1.0 / (1.0 + math.log(1.0 + 1))
    result = node_specificity(adj)
    assert result["A"] == pytest.approx(expected, rel=1e-9)


def test_node_specificity_degree_two():
    adj = {"A": {"B": 1.0, "C": 1.0}}
    expected = 1.0 / (1.0 + math.log(1.0 + 2))
    result = node_specificity(adj)
    assert result["A"] == pytest.approx(expected, rel=1e-9)


def test_node_specificity_higher_degree_scores_lower():
    # A hub with more neighbors should get a strictly lower specificity score
    # than a node with fewer neighbors (down-weighting generic hubs).
    adj = {
        "hub": {"n1": 1.0, "n2": 1.0, "n3": 1.0, "n4": 1.0},
        "leaf": {"n1": 1.0},
    }
    result = node_specificity(adj)
    assert result["hub"] < result["leaf"]


def test_node_specificity_multiple_nodes_exact_values():
    adj = {"A": {"B": 1.0, "C": 1.0, "D": 1.0}, "B": {"A": 1.0}}
    result = node_specificity(adj)
    expected_a = 1.0 / (1.0 + math.log(1.0 + 3))
    expected_b = 1.0 / (1.0 + math.log(1.0 + 1))
    assert result["A"] == pytest.approx(expected_a, rel=1e-9)
    assert result["B"] == pytest.approx(expected_b, rel=1e-9)

