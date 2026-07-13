import pytest
from rag_guard.guard import _content_tokens, groundedness, redact_pii

def test_content_tokens_empty_string_returns_empty_set():
    assert _content_tokens('') == set()
    assert _content_tokens(None) == set()

def test_groundedness_support_rounded_to_4_decimals():
    result = groundedness('alpha beta gamma', ['alpha'])
    expected_support = round(1 / 3, 4)
    assert result['support'] == pytest.approx(expected_support, rel=1e-09)
    assert result['support'] == pytest.approx(0.3333, rel=1e-09)

def test_redact_pii_email():
    text = 'Contact me at john.doe@example.com please.'
    result = redact_pii(text)
    assert result == 'Contact me at [redacted-email] please.'
    assert 'XX' not in result

def test_redact_pii_ssn():
    text = 'SSN: 123-45-6789 on file.'
    result = redact_pii(text)
    assert result == 'SSN: [redacted-ssn] on file.'
    assert 'XX' not in result

def test_redact_pii_phone():
    text = 'Call 555-123-4567 now.'
    result = redact_pii(text)
    assert result == 'Call [redacted-phone] now.'
    assert 'XX' not in result
