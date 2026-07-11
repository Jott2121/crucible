import pytest
from graph_guard.ppr import personalized_pagerank


def test_single_iteration_chain_with_dangling_and_hub():
    """Hand-computed single PPR iteration for a source node fanning out to two
    'neighbor-only' nodes that never appear as keys in adj (pure sinks)."""
    adj = {"a": {"b": 2.0, "c": 1.0}}
    result = personalized_pagerank(adj, ["a"], alpha=0.85, iters=1)

    # exact fractions worked out by hand:
    # nxt[b] = 0.85 * (1/3) * (2/3) = 17/90
    # nxt[c] = 0.85 * (1/3) * (1/3) = 17/180
    # dangling = 2/3 (from b and c each contributing 1/3)
    # mass = 0.15 + 0.85*(2/3) = 43/60
    # nxt[a] = mass = 43/60
    expected_a = 43.0 / 60.0
    expected_b = 17.0 / 90.0
    expected_c = 17.0 / 180.0

    assert result["a"] == pytest.approx(expected_a, rel=1e-9)
    assert result["b"] == pytest.approx(expected_b, rel=1e-9)
    assert result["c"] == pytest.approx(expected_c, rel=1e-9)
    # total mass must be conserved
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-9)


def test_single_iteration_all_dangling_nodes():
    """Both nodes have zero out-degree; after one iteration all rank mass must
    have flowed through the dangling redistribution + teleport back onto the
    single seed node."""
    adj = {"a": {}, "b": {}}
    result = personalized_pagerank(adj, ["a"], alpha=0.85, iters=1)

    # dangling = 0.5 (from a) + 0.5 (from b) = 1.0
    # mass = 0.15 + 0.85*1.0 = 1.0
    # nxt[a] = mass * 1.0 = 1.0, nxt[b] = 0.0 (no tele mass assigned to it)
    assert result["a"] == pytest.approx(1.0, rel=1e-9)
    assert result["b"] == pytest.approx(0.0, abs=1e-12)


def test_single_iteration_source_with_out_edges_and_dangling_target():
    """Source node 'a' has an explicit outgoing edge to dangling node 'b'
    (which is itself a key with an empty adjacency), exercising both the
    non-dangling propagation line and the dangling branch for a key that is
    present in adj with weight 0."""
    adj = {"a": {"b": 1.0}, "b": {}}
    result = personalized_pagerank(adj, ["a"], alpha=0.85, iters=1)

    # nxt[b] = 0.85 * 0.5 * (1.0/1.0) = 0.425
    # dangling = ru(b) = 0.5 (since b has zero out-sum)
    # mass = 0.15 + 0.85*0.5 = 0.575
    # nxt[a] = mass = 0.575
    assert result["a"] == pytest.approx(0.575, rel=1e-9)
    assert result["b"] == pytest.approx(0.425, rel=1e-9)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-9)


def test_convergence_sums_to_one_with_default_iters():
    """A general regression check that after full convergence the ranks still
    sum to ~1 for a small graph with both regular and dangling nodes."""
    adj = {
        "a": {"b": 1.0, "c": 1.0},
        "b": {"c": 1.0},
        "c": {},  # dangling
    }
    result = personalized_pagerank(adj, ["a"])
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    # every known node must be present in the result
    assert set(result.keys()) == {"a", "b", "c"}
