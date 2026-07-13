import pytest
from graph_guard.ppr import personalized_pagerank


def test_tol_strict_inequality_controls_convergence_break():
    """Targets the `delta < tol` vs `delta <= tol` mutation.

    We build a tiny 2-node graph where the personalization does not sit at a
    fixed point, so each iteration strictly changes the ranks.  We first grab
    the state after exactly one iteration (using tol=0.0, which never
    triggers an early break since delta after a real update is > 0).  We then
    measure the delta produced by that first iteration and feed it back in as
    `tol` for a 2-iteration run.

    With a *strict* less-than comparison (`delta < tol`), `delta == tol` does
    NOT satisfy the break condition, so the algorithm must proceed to a
    second iteration and return the iteration-2 ranks.  A mutant using
    `delta <= tol` would incorrectly break after the first iteration and
    return the iteration-1 ranks instead, which differ from the expected
    iteration-2 values computed independently below.
    """
    adj = {'A': {'B': 1.0}, 'B': {'A': 2.0}}
    seeds = ['A']
    alpha = 0.85

    # State after exactly one iteration (tol=0.0 guarantees no early break,
    # and this graph has no dangling nodes so it is unaffected by the other
    # mutants being investigated).
    rank_after_1 = personalized_pagerank(adj, seeds, alpha=alpha, iters=1, tol=0.0)

    rank0_A = 0.5
    rank0_B = 0.5
    delta1 = abs(rank_after_1['A'] - rank0_A) + abs(rank_after_1['B'] - rank0_B)

    # Use the measured delta as tol for a 2-iteration run.
    result = personalized_pagerank(adj, seeds, alpha=alpha, iters=2, tol=delta1)

    # Independently derive the expected iteration-2 ranks from the algorithm's
    # documented update rule, starting from the (analytically known) values
    # at iteration 1: A=0.575, B=0.425.
    rank1_A, rank1_B = 0.575, 0.425

    # iteration 2 update:
    nxt2_B = alpha * rank1_A * (1.0 / 1.0)
    nxt2_A = alpha * rank1_B * (2.0 / 2.0)
    mass = (1.0 - alpha)  # no dangling nodes here
    nxt2_A += mass * 1.0  # all teleport mass goes to seed 'A'

    expected_A = nxt2_A
    expected_B = nxt2_B

    assert result['A'] == pytest.approx(expected_A, rel=1e-6)
    assert result['B'] == pytest.approx(expected_B, rel=1e-6)

    # Sanity: this must differ from the (incorrect) iteration-1 result that a
    # non-strict comparison mutant would have returned.
    assert result['A'] != pytest.approx(rank1_A, rel=1e-6)


def test_dangling_node_handled_and_distribution_normalizes():
    """A node with no outgoing edges (C) must not crash the algorithm and the
    resulting scores must still form a valid probability distribution over
    all nodes referenced by the adjacency (including sink-only nodes)."""
    adj = {'A': {'B': 1.0}, 'B': {'C': 1.0}}
    result = personalized_pagerank(adj, ['A'], alpha=0.85, iters=50, tol=1e-9)

    assert set(result) == {'A', 'B', 'C'}
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
    for score in result.values():
        assert score >= 0.0
