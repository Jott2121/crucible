import pytest

from graph_guard.ppr import personalized_pagerank


class _HashChangingNode:
    def __init__(self):
        self._hash_calls = 0

    def __hash__(self):
        self._hash_calls += 1
        # Keep set membership valid, then arrange for the rank dictionary lookup
        # to succeed while the separately-built out_sum dictionary misses.
        values = [1, 1, 1, 1, 10, 20, 10, 10, 10]
        return values[self._hash_calls - 1] if self._hash_calls <= len(values) else 10


class _RowlessAdjacency:
    def __init__(self, node):
        self.node = node

    def __iter__(self):
        return iter((self.node,))

    def values(self):
        return iter(({},))

    def get(self, key, default=None):
        return {}


def test_missing_out_sum_entry_is_treated_as_a_dangling_node():
    node = _HashChangingNode()
    adjacency = _RowlessAdjacency(node)

    scores = personalized_pagerank(
        adjacency, [node], alpha=0.5, iters=1, tol=0.0
    )

    # The sole node is dangling, so all of its mass is teleported back to itself.
    assert scores[node] == pytest.approx(1.0, rel=1e-6)


class _RowDisappearingAdjacency:
    def __init__(self):
        self.source_gets = 0

    def __iter__(self):
        return iter(("source", "target"))

    def values(self):
        return iter(({}, {}))

    def get(self, key, default=None):
        if key == "source":
            self.source_gets += 1
            if self.source_gets == 1:
                return {"target": 1.0}
        return default


def test_missing_row_during_distribution_is_an_empty_adjacency_row():
    adjacency = _RowDisappearingAdjacency()

    scores = personalized_pagerank(
        adjacency, ["source"], alpha=0.5, iters=1, tol=0.0
    )

    # Initial ranks are 0.5 each. The target is dangling and contributes 0.25
    # through alpha; the source's row has disappeared and contributes no edge
    # mass, leaving teleport mass 0.75 entirely on the source.
    assert scores["source"] == pytest.approx(0.75, rel=1e-6)
    assert scores["target"] == pytest.approx(0.0, abs=1e-12)
