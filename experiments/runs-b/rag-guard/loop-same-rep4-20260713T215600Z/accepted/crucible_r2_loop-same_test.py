import pytest
from rag_guard.guard import groundedness


def test_groundedness_support_rounded_to_4_decimals():
    # 1/3 = 0.333333... -> round to 4 decimals = 0.3333, not 0.33333
    answer = "alpha beta gamma"
    contexts = ["alpha unrelated unrelated"]
    result = groundedness(answer, contexts, threshold=0.0)
    assert result["support"] == pytest.approx(0.3333, rel=1e-6)
    # ensure it is NOT rounded to 5 decimals (which would be 0.33333)
    assert result["support"] != pytest.approx(0.33333, rel=1e-9)
