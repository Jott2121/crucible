import pytest

from graph_guard.ppr import personalized_pagerank


class _HashChangesOnlyForOutSumLookup:
    def __init__(self):
        self.calls = 0

    def __hash__(self):
        self.calls += 1
        # During this one-node invocation, call 9 is specifically the
        # out_sum.get(u, default) lookup in the first iteration.
        return 999_983 if self.calls == 9 else 17


class _ResettingSeeds:
    def __init__(self, node):
        self.node = node

    def __iter__(self):
        self.node.calls = 0
        yield self.node


def test_pagerank_treats_missing_out_sum_entry_as_dangling():
    node = _HashChangesOnlyForOutSumLookup()
    adjacency = {node: {}}

    result = personalized_pagerank(
        adjacency,
        _ResettingSeeds(node),
        alpha=0.85,
        iters=1,
    )

    # A sole dangling node has all of its rank redistributed through the
    # personalized teleport distribution, which contains only itself.
    assert result[node] == pytest.approx(1.0, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
