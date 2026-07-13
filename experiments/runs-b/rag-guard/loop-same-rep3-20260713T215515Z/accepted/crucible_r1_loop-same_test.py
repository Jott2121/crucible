import pytest
from rag_guard.guard import _content_tokens, groundedness, redact_pii

def test_content_tokens_empty_string_returns_empty_set():
    assert _content_tokens('') == set()

def test_groundedness_support_rounds_to_four_decimals():
    answer = 'alpha beta gamma'
    contexts = ['alpha']
    result = groundedness(answer, contexts, threshold=0.5)
    expected = round(1 / 3, 4)
    assert result['support'] == pytest.approx(expected, rel=1e-06)
    assert result['support'] != round(1 / 3, 5)
