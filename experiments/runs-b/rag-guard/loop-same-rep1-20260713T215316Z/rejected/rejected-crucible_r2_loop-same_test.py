import pytest
from rag_guard.guard import redact_pii


def test_redact_pii_card_number_exact_replacement():
    text = "My card number is 4111111111111111 please charge it"
    result = redact_pii(text)
    assert "[redacted-card]" in result
    assert "XX[redacted-card]XX" not in result
    assert result == "My card number is [redacted-card] please charge it"
