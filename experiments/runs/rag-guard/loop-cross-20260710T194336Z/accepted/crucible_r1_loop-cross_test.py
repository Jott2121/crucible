import pytest

from rag_guard.guard import groundedness


def test_empty_context_does_not_support_answer_token():
    result = groundedness("xxxx", [""])

    assert result["grounded"] is False
    assert result["support"] == pytest.approx(0.0, rel=1e-6)


def test_groundedness_support_is_rounded_to_four_decimal_places():
    answer = "alpha bravo charlie delta echo foxtrot"
    contexts = ["alpha"]

    result = groundedness(answer, contexts)

    assert result["grounded"] is False
    assert result["support"] == pytest.approx(0.1667, rel=1e-6)
