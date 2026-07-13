import math
import pytest
from graph_guard.ppr import personalized_pagerank

def test_dangling_nodes_redistribute_all_mass_to_seed():
    adj = {'A': {}, 'B': {}}
    rank = personalized_pagerank(adj, seeds=['A'])
    assert rank['A'] == pytest.approx(1.0, abs=1e-06)
    assert rank['B'] == pytest.approx(0.0, abs=1e-06)
    assert sum(rank.values()) == pytest.approx(1.0, rel=1e-06)
