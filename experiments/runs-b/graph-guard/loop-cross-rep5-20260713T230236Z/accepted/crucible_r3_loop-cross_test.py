import inspect

import pytest

from graph_guard.ppr import personalized_pagerank


class _LookupMissNode:
    """Behaves normally except for one deliberate out_sum lookup."""

    def __init__(self):
        self._forced_miss = False

    def __hash__(self):
        caller = inspect.currentframe().f_back
        if (
            caller.f_code.co_name == "personalized_pagerank"
            and "ru" in caller.f_locals
            and not self._forced_miss
        ):
            self._forced_miss = True
            return 1
        return 0


def test_dangling_node_uses_zero_default_when_out_sum_lookup_misses():
    node = _LookupMissNode()

    result = personalized_pagerank({node: {}}, [node], alpha=0.85, iters=1)

    # A sole dangling node redistributes all of its rank to its sole seed.
    assert result[node] == pytest.approx(1.0, rel=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, rel=1e-6)
