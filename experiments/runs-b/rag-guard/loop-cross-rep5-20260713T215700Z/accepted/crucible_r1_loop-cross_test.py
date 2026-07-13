import pytest

from rag_guard.guard import groundedness, redact_pii


def test_groundedness_empty_answer_is_never_grounded_even_at_zero_threshold():
    result = groundedness("", [], threshold=0.0)

    assert result["grounded"] is False
    assert result["support"] == pytest.approx(0.0)


def test_groundedness_support_is_rounded_to_four_decimal_places():
    result = groundedness(
        "alpha bravo charlie delta echo foxtrot",
        ["alpha"],
        threshold=0.2,
    )

    assert result["grounded"] is False
    assert result["support"] == pytest.approx(0.1667, rel=1e-6)


def test_redact_pii_uses_exact_standard_replacement_markers():
    text = (
        "Email alice@example.com; SSN 123-45-6789; "
        "phone 555-123-4567; card 4111 1111 1111 1111."
    )

    assert redact_pii(text) == (
        "Email [redacted-email]; SSN [redacted-ssn]; "
        "phone [redacted-phone]; card [redacted-card]."
    )
