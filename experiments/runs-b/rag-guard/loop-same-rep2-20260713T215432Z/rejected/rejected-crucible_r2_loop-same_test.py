import pytest
from rag_guard.guard import redact_pii


def test_redact_pii_card_exact_replacement():
    text = "Card number: 1234 5678 9012 3456 thanks"
    result = redact_pii(text)
    assert result == "Card number: [redacted-card] thanks"
    assert "XX[redacted-card]XX" not in result
