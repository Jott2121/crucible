import pytest
from graph_guard.ppr import personalized_pagerank


def test_seed_teleport_accumulates_duplicate_seeds():
    """Mutant x_personalized_pagerank__mutmut_16 replaces `tele.get(s, 0.0)` with
    `tele.get(None, 0.0)`, so repeated seeds no longer accumulate their teleport mass.
    With an edgeless graph, PPR converges exactly to the teleport vector, so we can
    check the accumulated values directly."""
    adj = {"a": {}, "b": {}}
    result = personalized_pagerank(adj, ["a", "a", "b"])
    assert result["a"] == pytest.approx(2.0 / 3.0, rel=1e-6)
    assert result["b"] == pytest.approx(1.0 / 3.0, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)


def test_default_iters_matches_explicit_fifty():
    """Mutant x_personalized_pagerank__mutmut_2 changes the default `iters` from 50 to 51.
    Using tol=0.0 forces the loop to always run exactly `iters` iterations (no early
    stop), so the default-parameter call must match an explicit iters=50 call on a
    slowly-converging graph."""
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    r_explicit = personalized_pagerank(adj, ["a"], alpha=0.85, iters=50, tol=0.0)
    r_default = personalized_pagerank(adj, ["a"], alpha=0.85, tol=0.0)
    for k in r_explicit:
        assert r_default[k] == pytest.approx(r_explicit[k], rel=1e-9)


def test_dangling_mass_accumulates_across_nodes():
    """Mutant x_personalized_pagerank__mutmut_47 replaces `dangling += ru` with
    `dangling = ru`, so dangling mass from multiple sink nodes is not summed.
    With two dangling nodes and one seeded outgoing node, run exactly one iteration
    (iters=1) and check the resulting distribution."""
    adj = {"a": {}, "b": {}, "c": {"a": 1.0}}
    result = personalized_pagerank(adj, ["c"], alpha=0.85, iters=1, tol=0.0)

    alpha = 0.85
    expected_a = alpha * (1.0 / 3.0) * 1.0  # edge c->a fully weighted
    dangling = 1.0 / 3.0 + 1.0 / 3.0  # both 'a' and 'b' are dangling initially
    mass = (1.0 - alpha) + alpha * dangling
    expected_c = mass * 1.0  # all teleport mass goes to seed 'c'
    expected_b = 0.0

    assert result["a"] == pytest.approx(expected_a, rel=1e-6)
    assert result["b"] == pytest.approx(expected_b, abs=1e-9)
    assert result["c"] == pytest.approx(expected_c, rel=1e-6)


def test_early_stop_requires_strictly_less_than_tol():
    """Mutant x_personalized_pagerank__mutmut_72 changes `delta < tol` to `delta <= tol`,
    so when the delta exactly equals tol the mutant stops one iteration early. We craft
    a case where after iteration 1 delta == tol exactly (both 0.5), so the original
    code must continue to iteration 2, while the mutant would stop at iteration 1."""
    adj = {"a": {}, "b": {"a": 1.0}}
    result = personalized_pagerank(adj, ["b"], alpha=0.5, iters=2, tol=0.5)

    # Manually unrolled iterations (alpha=0.5, seed='b', edge b->a weight 1):
    # iter1: a=0.25, b=0.75 (delta from uniform 0.5/0.5 is exactly 0.5)
    # since delta(0.5) is NOT < tol(0.5), original continues to iter2:
    # iter2: a=0.375, b=0.625
    expected_a = 0.375
    expected_b = 0.625

    assert result["a"] == pytest.approx(expected_a, rel=1e-9)
    assert result["b"] == pytest.approx(expected_b, rel=1e-9)


def test_convergence_check_uses_difference_not_sum():
    """Mutant x_personalized_pagerank__mutmut_70 replaces `nxt[v] - rank[v]` with
    `nxt[v] + rank[v]` inside the delta computation, which (since all values are
    non-negative and roughly sum to 1 each iteration) makes delta stay near 2 and
    thus never trigger early stopping. We choose a tol large enough that the
    original algorithm truly stops after iteration 1, while the mutant is forced
    to keep going to iteration 2, producing a different, distinguishable result."""
    adj = {"a": {}, "b": {}, "c": {"a": 1.0}}
    result = personalized_pagerank(adj, ["c"], alpha=0.85, iters=2, tol=0.8)

    alpha = 0.85
    expected_a = alpha / 3.0
    dangling = 2.0 / 3.0
    mass = (1.0 - alpha) + alpha * dangling
    expected_c = mass
    expected_b = 0.0

    assert result["a"] == pytest.approx(expected_a, rel=1e-6)
    assert result["b"] == pytest.approx(expected_b, abs=1e-9)
    assert result["c"] == pytest.approx(expected_c, rel=1e-6)
