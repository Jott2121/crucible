import pytest
from rag_guard.guard import _content_tokens, redact_pii, groundedness


def test_content_tokens_empty_string_returns_empty_set():
    # If text is empty string, `text or "XXXX"` mutant would produce tokens
    # from "xxxx" instead of an empty set.
    assert _content_tokens("") == set()
    assert _content_tokens(None) == set()


def test_redact_pii_email_exact_replacement():
    text = "Contact me at john.doe@example.com please"
    result = redact_pii(text)
    assert result == "Contact me at [redacted-email] please"
    assert "XX" not in result


def test_groundedness_with_empty_answer_uses_empty_content_tokens():
    # relies on _content_tokens("") == set() for correct behavior
    result = groundedness("", ["some context here"])
    assert result == {"grounded": False, "support": 0.0}
