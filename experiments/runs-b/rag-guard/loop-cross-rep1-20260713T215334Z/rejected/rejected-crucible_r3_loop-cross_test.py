from rag_guard.guard import redact_pii


def test_redact_pii_replaces_card_number_with_exact_card_placeholder():
    text = "Please charge card 4111 1111 1111 1111 for the order."
    expected = "Please charge card [redacted-card] for the order."

    assert redact_pii(text) == expected
