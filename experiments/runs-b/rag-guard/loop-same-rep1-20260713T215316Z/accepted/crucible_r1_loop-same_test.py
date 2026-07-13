import pytest
from rag_guard.guard import _content_tokens, redact_pii, should_refuse

def test_content_tokens_empty_string_returns_empty_set():
    assert _content_tokens('') == set()
    assert _content_tokens(None) == set()

def test_should_refuse_default_threshold_boundary():
    hits = [{'score': 0.1}]
    assert should_refuse(hits) is False
    hits_eq = [{'score': 0.05}]
    assert should_refuse(hits_eq) is False
    hits_low = [{'score': 0.01}]
    assert should_refuse(hits_low) is True
