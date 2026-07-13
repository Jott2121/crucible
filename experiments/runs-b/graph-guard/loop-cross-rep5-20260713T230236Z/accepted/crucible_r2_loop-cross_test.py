import inspect

import pytest

import graph_guard.ppr as ppr


class _OutSumLookupMissNode:
    """Returns a different hash only while PPR looks up its out_sum entry."""

    target_line = None

    def __hash__(self):
        caller = inspect.currentframe().f_back
        if (
            caller.f_code is ppr.personalized_pagerank.__code__
            and caller.f_lineno == self.target_line
        ):
            return 101
        return 17


def test_pagerank_treats_missing_out_sum_as_dangling():
    source, first_line = inspect.getsourcelines(ppr.personalized_pagerank)
    _OutSumLookupMissNode.target_line = next(
        first_line + offset
        for offset, line in enumerate(source)
        if line.strip().startswith("s = out_sum.get(")
    )

    node = _OutSumLookupMissNode()
    result = ppr.personalized_pagerank({node: {}}, [node], alpha=0.85, iters=1)

    # The sole node is dangling, so all mass is teleported back to its seed.
    assert result[node] == pytest.approx(1.0, rel=1e-6)


class _SelfRemovingWeights(dict):
    def __init__(self, owner, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def values(self):
        self.owner.pop("a", None)
        return super().values()


def test_pagerank_uses_empty_adjacency_default_for_row_removed_after_outsum():
    adj = {}
    adj["a"] = _SelfRemovingWeights(adj, {"b": 1.0})

    result = ppr.personalized_pagerank(adj, ["a"], alpha=0.5, iters=1)

    # Initial ranks are 1/2 each.  "a" retains a positive precomputed out_sum
    # but has no row when edges are traversed; only dangling "b" contributes
    # 1/2 dangling mass.  Thus teleport mass is .5 + .5*.5 = .75.
    assert result["a"] == pytest.approx(0.75, rel=1e-6)
    assert result["b"] == pytest.approx(0.0, abs=1e-12)
