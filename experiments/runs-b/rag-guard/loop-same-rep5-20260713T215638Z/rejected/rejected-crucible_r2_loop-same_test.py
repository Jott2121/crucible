import pytest
from rag_guard.guard import redact_pii


def test_redact_pii_card_number_exact_replacement():
    text = "Card: 1234 5678 9012 3456 end"
    result = redact_pii(text)
    assert result == "Card: [redacted-card] end"
    assert "XX" not in result
