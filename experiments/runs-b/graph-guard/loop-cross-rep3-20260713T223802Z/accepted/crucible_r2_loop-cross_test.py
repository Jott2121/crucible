import pytest

from graph_guard.ppr import personalized_pagerank


class _HashChangingNode:
    def __init__(self):
        self.hash_value = 11

    def __hash__(self):
        return self.hash_value


class _AdjacencyWithDelayedHashChange(dict):
    def __init__(self, node):
        super().__init__({node: {}})
        self.node = node
        self.changed = False

    def get(self, key, default=None):
        value = super().get(key, default)
        if not self.changed:
            self.changed = True
            self.node.hash_value = 29
        return value


class _ResettingIterationCount:
    def __init__(self, node):
        self.node = node

    def __index__(self):
        self.node.hash_value = 11
        return 1


def test_pagerank_treats_missing_out_sum_entry_as_dangling():
    node = _HashChangingNode()
    adj = _AdjacencyWithDelayedHashChange(node)

    result = personalized_pagerank(
        adj,
        [node],
        alpha=0.85,
        iters=_ResettingIterationCount(node),
    )

    # The sole node is dangling and is also the sole teleport destination, so
    # its complete rank mass must remain on itself after one iteration.
    assert result[node] == pytest.approx(1.0, rel=1e-6)
