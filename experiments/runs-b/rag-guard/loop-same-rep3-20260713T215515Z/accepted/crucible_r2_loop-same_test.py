import pytest
from rag_guard.guard import redact_pii

def test_redact_pii_card_number_lowercase_tag():
    text = '1234567890123'
    result = redact_pii(text)
    assert '[redacted-card]' in result
    assert '[REDACTED-CARD]' not in result
    assert 'XX[redacted-card]XX' not in result
