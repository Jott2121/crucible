import math
import pytest

from graph_guard.ppr import personalized_pagerank


def _reference_ppr(adj, seeds, *, alpha, iters, tol):
    """Independent transcription of the documented PPR power-iteration algorithm,
    used only to pin down expected values for explicit (trusted) parameters so we
    can check that the function's *defaults* match those values."""
    nodes = set(adj)
    for nbrs in adj.values():
        nodes.update(nbrs)
    if not nodes:
        return {}
    valid = [s for s in seeds if s in nodes]
    if not valid:
        valid = list(nodes)
    tele = {}
    for s in valid:
        tele[s] = tele.get(s, 0.0) + 1.0 / len(valid)
    n = len(nodes)
    rank = {v: 1.0 / n for v in nodes}
    out_sum = {u: sum(adj.get(u, {}).values()) for u in nodes}
    for _ in range(iters):
        nxt = {v: 0.0 for v in nodes}
        dangling = 0.0
        for u in nodes:
            ru = rank[u]
            s = out_sum.get(u, 0.0)
            if s <= 0:
                dangling += ru
                continue
            for v, w in adj.get(u, {}).items():
                nxt[v] += alpha * ru * (w / s)
        mass = (1.0 - alpha) + alpha * dangling
        for sd, p in tele.items():
            nxt[sd] += mass * p
        delta = sum(abs(nxt[v] - rank[v]) for v in nodes)
        rank = nxt
        if delta < tol:
            break
    return rank


def test_duplicate_seed_accumulates_teleport_mass():
    # All nodes are dangling (no outgoing edges), so after one iteration the
    # rank equals the teleport distribution exactly, and it is stable from then on.
    adj = {"a": {}, "b": {}, "c": {}}
    seeds = ["a", "a", "b"]  # 'a' appears twice -> should get 2/3 of teleport mass
    result = personalized_pagerank(adj, seeds)

    assert result["a"] == pytest.approx(2.0 / 3.0, rel=1e-9)
    assert result["b"] == pytest.approx(1.0 / 3.0, rel=1e-9)
    assert result["c"] == pytest.approx(0.0, abs=1e-9)


def test_two_node_cycle_stops_exactly_when_delta_is_strictly_below_tol():
    # Hand-derived exact recurrence for a 2-node cycle a<->b, seed on 'a', alpha=0.5:
    #   x0=y0=0.5
    #   x1 = alpha*y0 + (1-alpha) = 0.75 ; y1 = alpha*x0 = 0.25
    #   delta1 = |x1-x0| + |y1-y0| = 0.25 + 0.25 = 0.5  (== tol chosen below)
    #   x2 = alpha*y1 + (1-alpha) = 0.625 ; y2 = alpha*x1 = 0.375
    #   delta2 = |x2-x1| + |y2-y1| = 0.125 + 0.125 = 0.25 (< tol -> stop here)
    #
    # With a strict "<" comparison, iteration 1 (delta==tol) must NOT stop the
    # loop, so the final answer is the iteration-2 values (0.625, 0.375).
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    seeds = ["a"]

    result = personalized_pagerank(adj, seeds, alpha=0.5, tol=0.5)

    assert result["a"] == pytest.approx(0.625, rel=1e-9)
    assert result["b"] == pytest.approx(0.375, rel=1e-9)


def test_default_iters_and_tol_match_trusted_reference():
    # A slowly-mixing 2-node cycle at the real default alpha (0.85) does not
    # converge to 1e-9 within 50 iterations, so the exact default iteration
    # count and tolerance both matter for the returned values.
    adj = {"a": {"b": 1.0}, "b": {"a": 1.0}}
    seeds = ["a"]

    expected = _reference_ppr(adj, seeds, alpha=0.85, iters=50, tol=1e-9)
    result = personalized_pagerank(adj, seeds)  # relies on documented defaults

    assert result["a"] == pytest.approx(expected["a"], rel=1e-9, abs=1e-12)
    assert result["b"] == pytest.approx(expected["b"], rel=1e-9, abs=1e-12)
