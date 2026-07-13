from rag_guard.guard import _content_tokens, redact_pii, should_refuse

def test_content_tokens_none_is_empty_set():
    assert _content_tokens(None) == set()

def test_should_refuse_default_accepts_strong_retrieval_hit():
    hits = [{'score': 0.8}, {'score': 0.1}]
    assert should_refuse(hits) is False
