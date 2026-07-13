import pytest

from rag_guard.guard import _content_tokens, groundedness, redact_pii


def test_content_tokens_none_is_empty_set():
    assert _content_tokens(None) == set()


def test_groundedness_support_is_rounded_to_four_decimal_places():
    result = groundedness("alpha beta gamma", ["alpha beta"])

    assert result["grounded"] is True
    assert result["support"] == pytest.approx(0.6667, rel=1e-6)


def test_redact_pii_uses_exact_standard_placeholders():
    text = (
        "Email jane.doe+alerts@example.com, SSN 123-45-6789, "
        "phone 555-123-4567, card 4111 1111 1111 1111."
    )

    expected = (
        "Email [redacted-email], SSN [redacted-ssn], "
        "phone [redacted-phone], card [redacted-card]."
    )

    assert redact_pii(text) == expected
