import pytest

from rag_guard.guard import _content_tokens, groundedness, redact_pii


def test_content_tokens_treats_none_as_empty_text():
    assert _content_tokens(None) == set()


def test_groundedness_support_is_rounded_to_four_decimal_places():
    answer = "alpha bravo charlie delta echo foxtrot"
    contexts = ["alpha"]

    result = groundedness(answer, contexts)

    assert result["grounded"] is False
    assert result["support"] == pytest.approx(round(1 / 6, 4), rel=1e-6)


def test_redact_pii_uses_exact_standard_masks_for_all_supported_pii_types():
    text = (
        "Email alice@example.com; "
        "SSN 123-45-6789; "
        "phone 555-123-4567; "
        "card 4111 1111 1111 1111."
    )

    assert redact_pii(text) == (
        "Email [redacted-email]; "
        "SSN [redacted-ssn]; "
        "phone [redacted-phone]; "
        "card [redacted-card]."
    )
