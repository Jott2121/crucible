import math
import pytest

from graph_guard.ppr import personalized_pagerank


def _sim_two_node(alpha, tol, iters):
    """Independent reference simulation of PPR on the 2-node cycle
    A<->B (each edge weight 1.0), seeded entirely on 'A'.

    This mirrors the mathematically documented behaviour of
    personalized_pagerank (power iteration with teleport + early
    stopping on L1 delta), implemented from scratch (not by calling
    the module under test) so it can serve as an independently
    computed oracle.
    """
    b = 1.0 - alpha
    x, y = 0.5, 0.5  # uniform initial rank over 2 nodes
    for _ in range(iters):
        nx = alpha * y + b   # A receives teleport mass (b) + inflow from B
        ny = alpha * x        # B receives inflow from A only
        delta = abs(nx - x) + abs(ny - y)
        x, y = nx, ny
        if delta < tol:
            break
    return x, y


def test_duplicate_seed_teleport_distribution():
    # No edges at all -> every node is dangling every iteration, so the
    # rank converges exactly to the teleport distribution built from
    # `seeds`. With seeds=['A', 'A', 'B'] (A repeated), the correct
    # teleport mass split is A:2/3, B:1/3 (duplicates should accumulate).
    adj = {"A": {}, "B": {}}
    result = personalized_pagerank(adj, ["A", "A", "B"], iters=10, tol=1e-12)

    assert result["A"] == pytest.approx(2.0 / 3.0, rel=1e-6)
    assert result["B"] == pytest.approx(1.0 / 3.0, rel=1e-6)
    assert result["A"] + result["B"] == pytest.approx(1.0, rel=1e-6)


def test_default_parameters_precise_convergence():
    # A 2-node bidirectional cycle with default alpha/iters/tol. Since the
    # contraction factor is alpha=0.85, the process has NOT reached the
    # 1e-9 tolerance by 50 iterations (error scale ~alpha**50 ~ 3e-4), so
    # the exact default iteration count and tolerance both matter for the
    # final numeric result.
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}

    result = personalized_pagerank(adj, ["A"])  # defaults: alpha=0.85, iters=50, tol=1e-9

    expected_x, expected_y = _sim_two_node(alpha=0.85, tol=1e-9, iters=50)

    assert result["A"] == pytest.approx(expected_x, rel=1e-6)
    assert result["B"] == pytest.approx(expected_y, rel=1e-6)


def test_asymmetric_adjacency_no_crash_and_matches_expected_values():
    # 'B' only appears as a neighbor value, never as a key in `adj`.
    # The implementation must fall back to an empty neighbor dict for such
    # nodes (adj.get(u, {})) rather than crashing. Mathematically, this
    # dangling-node behaviour is equivalent to the explicit 2-node cycle
    # (B's mass returns to the sole seed A via teleport instead of an
    # explicit back-edge), so the same reference recurrence applies.
    adj = {"A": {"B": 1.0}}  # B not a key

    result = personalized_pagerank(adj, ["A"])  # should not raise

    expected_x, expected_y = _sim_two_node(alpha=0.85, tol=1e-9, iters=50)

    assert result["A"] == pytest.approx(expected_x, rel=1e-6)
    assert result["B"] == pytest.approx(expected_y, rel=1e-6)
    assert result["A"] + result["B"] == pytest.approx(1.0, rel=1e-6)


def test_early_stopping_uses_correct_delta_sign():
    # Use a loose explicit tol so that the *correct* delta computation
    # (L1 distance between successive iterates) triggers early stopping
    # well before `iters` is exhausted, and compare against an
    # independently computed reference that stops on the same criterion.
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}

    result = personalized_pagerank(adj, ["A"], alpha=0.85, iters=50, tol=0.1)

    expected_x, expected_y = _sim_two_node(alpha=0.85, tol=0.1, iters=50)

    # Sanity: the reference oracle should indeed stop well before 50 iters
    # (i.e. not have fully converged to the ~0.5405/0.4595 fixed point).
    assert expected_x != pytest.approx(0.5405286, rel=1e-3)

    assert result["A"] == pytest.approx(expected_x, rel=1e-6)
    assert result["B"] == pytest.approx(expected_y, rel=1e-6)
