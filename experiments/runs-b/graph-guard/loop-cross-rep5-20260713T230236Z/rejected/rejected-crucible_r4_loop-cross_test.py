import pytest

from graph_guard.ppr import personalized_pagerank


class _HashChangingNode:
    def __init__(self):
        self.armed = False
        self.calls_after_arming = 0

    def __hash__(self):
        if not self.armed:
            return 101
        self.calls_after_arming += 1
        # The adjacency lookup, out_sum insertion, and rank lookup retain
        # the original hash; the subsequent out_sum lookup does not.
        return 101 if self.calls_after_arming <= 3 else 202


class _ArmingAdjacency(dict):
    def __init__(self, special_node, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.special_node = special_node
        self.has_armed = False

    def get(self, key, default=None):
        if key is self.special_node and not self.has_armed:
            self.special_node.armed = True
            self.has_armed = True
        return super().get(key, default)


def test_pagerank_treats_missing_out_sum_entry_as_dangling():
    dangling = _HashChangingNode()
    adj = _ArmingAdjacency(dangling, {"root": {dangling: 1.0}})

    rank = personalized_pagerank(adj, ["root"], alpha=0.5, iters=1, tol=0.0)

    # Initially root and dangling each have 0.5 rank. Root sends 0.25 to
    # dangling; dangling contributes its 0.5 as dangling mass, so teleport
    # back to root is 0.5 + 0.5 * 0.5 = 0.75.
    assert rank["root"] == pytest.approx(0.75, rel=1e-6)
