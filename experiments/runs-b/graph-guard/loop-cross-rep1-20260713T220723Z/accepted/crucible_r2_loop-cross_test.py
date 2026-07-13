import inspect
import linecache

import pytest

from graph_guard.ppr import personalized_pagerank


class _NodeMissingOnlyFromOutSum:
    """Uses a different hash only for the loop's out_sum lookup."""

    def __hash__(self):
        caller = inspect.currentframe().f_back
        source_line = linecache.getline(caller.f_code.co_filename, caller.f_lineno)
        if "out_sum.get(u" in source_line:
            return 1_000_003
        return 17

    def __eq__(self, other):
        return self is other


def test_pagerank_treats_missing_out_sum_entry_as_dangling():
    source = _NodeMissingOnlyFromOutSum()
    target = "target"
    adjacency = {source: {target: 1.0}}

    # With one initial iteration, both nodes start at 1/2.  The deliberately
    # missing out_sum lookup must use the documented zero default, making both
    # nodes dangling; all mass is therefore teleported to the source seed.
    result = personalized_pagerank(
        adjacency,
        [source],
        alpha=0.5,
        iters=1,
        tol=0.0,
    )

    assert result[source] == pytest.approx(1.0, rel=1e-6)
    assert result[target] == pytest.approx(0.0, abs=1e-12)
