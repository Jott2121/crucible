import pytest

from graph_guard.ppr import personalized_pagerank


def test_duplicate_seeds_are_weighted_by_multiplicity():
    """mutmut_16: tele.get(None, ...) breaks accumulation for duplicate seeds.

    With seeds ['A', 'A', 'B'] on two isolated (dangling) nodes, the correct
    teleport vector should end up as {'A': 2/3, 'B': 1/3} (A appears twice),
    and since both nodes are pure sinks with no out-edges, the PPR result
    converges exactly to that teleport vector (mass is always fully
    redistributed every iteration because dangling reclaims the whole mass).
    """
    adj = {"A": {}, "B": {}}
    seeds = ["A", "A", "B"]
    result = personalized_pagerank(adj, seeds, alpha=0.85, iters=50, tol=1e-9)

    assert result["A"] == pytest.approx(2.0 / 3.0, rel=1e-6)
    assert result["B"] == pytest.approx(1.0 / 3.0, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_default_iters_is_fifty():
    """mutmut_2: default iters changed from 50 to 51.

    Force the loop to run exactly `iters` times (tol=0.0 can never trigger an
    early break since delta is always >= 0), then compare the default call
    against an explicit iters=50 call. On a 3-cycle that has not yet reached
    an exact fixed point after 50 rounds, running one extra round changes
    the values measurably, so this distinguishes iters=50 from iters=51.
    """
    adj = {"A": {"B": 1.0}, "B": {"C": 1.0}, "C": {"A": 1.0}}
    seeds = ["A"]

    r_default = personalized_pagerank(adj, seeds, tol=0.0)
    r_fixed = personalized_pagerank(adj, seeds, iters=50, tol=0.0)

    for node in adj:
        assert r_default[node] == pytest.approx(r_fixed[node], rel=1e-12)


def test_default_tol_is_1e_minus_9():
    """mutmut_3: default tol changed from 1e-9 to a huge value (>1.0).

    With a correct tiny default tol, calling without `tol` must match an
    explicit tol=1e-9 call (both run to the same convergence). If the
    default tol were huge, the no-tol call would stop after the very first
    iteration, producing a clearly less-converged (different) result on a
    cycle graph that needs several iterations to settle.
    """
    adj = {"A": {"B": 1.0}, "B": {"C": 1.0}, "C": {"A": 1.0}}
    seeds = ["A"]

    r_default = personalized_pagerank(adj, seeds, iters=50)
    r_explicit = personalized_pagerank(adj, seeds, iters=50, tol=1e-9)

    for node in adj:
        assert r_default[node] == pytest.approx(r_explicit[node], rel=1e-9)


def test_delta_uses_subtraction_not_addition():
    """mutmut_70: delta computed as |nxt + rank| instead of |nxt - rank|.

    On a simple 2-node mutual-edge graph seeded on 'A', after exactly one
    iteration the true delta (|nxt-rank| summed) is 0.15, which is below
    tol=0.5, so the correct implementation stops after iteration 1 and
    returns the iteration-1 values. If delta used addition instead, the
    computed "delta" would be ~2.0 (never below 0.5), so the loop would keep
    iterating well past the expected values checked here.
    """
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    seeds = ["A"]
    alpha = 0.85

    # Manually replicate iteration 1 exactly as the source code computes it.
    nxt_b1 = alpha * 0.5 * (1.0 / 1.0)
    mass1 = (1.0 - alpha) + alpha * 0.0
    nxt_a1 = alpha * 0.5 * (1.0 / 1.0) + mass1 * 1.0

    result = personalized_pagerank(adj, seeds, alpha=alpha, tol=0.5)

    assert result["A"] == pytest.approx(nxt_a1, rel=1e-6)
    assert result["B"] == pytest.approx(nxt_b1, rel=1e-6)


def test_break_condition_is_strictly_less_than():
    """mutmut_72: `delta <= tol` instead of `delta < tol`.

    Choose tol exactly equal to the delta produced after iteration 1 on a
    2-node mutual-edge graph. With the correct strict '<' comparison, this
    equality does NOT trigger a break, so a second iteration runs (whose
    delta is smaller and does satisfy '<'), yielding the iteration-2 values.
    With '<=' the loop would incorrectly stop after iteration 1 already,
    yielding different (iteration-1) values.
    """
    adj = {"A": {"B": 1.0}, "B": {"A": 1.0}}
    seeds = ["A"]
    alpha = 0.85

    # Iteration 1, replicated exactly as the source computes it.
    nxt_b1 = alpha * 0.5 * (1.0 / 1.0)
    mass1 = (1.0 - alpha) + alpha * 0.0
    nxt_a1 = alpha * 0.5 * (1.0 / 1.0) + mass1 * 1.0
    delta1 = abs(nxt_a1 - 0.5) + abs(nxt_b1 - 0.5)

    tol = delta1  # exactly equal to the first delta

    # Iteration 2, replicated exactly as the source computes it.
    nxt_b2 = alpha * nxt_a1 * (1.0 / 1.0)
    mass2 = (1.0 - alpha) + alpha * 0.0
    nxt_a2 = alpha * nxt_b1 * (1.0 / 1.0) + mass2 * 1.0

    result = personalized_pagerank(adj, seeds, alpha=alpha, tol=tol)

    assert result["A"] == pytest.approx(nxt_a2, rel=1e-9)
    assert result["B"] == pytest.approx(nxt_b2, rel=1e-9)
