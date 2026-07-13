import pytest

from rag_guard.guard import _content_tokens, groundedness, redact_pii


def test_content_tokens_empty_text_has_no_placeholder_token():
    assert _content_tokens("") == set()


def test_groundedness_support_is_rounded_to_four_decimal_places():
    answer = "alpha bravo charlie delta echo foxtrot"
    contexts = ["alpha"]

    result = groundedness(answer, contexts, threshold=0.1)

    assert result["grounded"] is True
    assert result["support"] == pytest.approx(0.1667, rel=1e-6)


def test_redact_pii_replaces_card_with_standard_card_marker_only():
    text = "Card number: 4111 1111 1111 1111."

    assert redact_pii(text) == "Card number: [redacted-card]."
