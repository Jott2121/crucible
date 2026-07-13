import pytest
from rag_guard.guard import _content_tokens, groundedness, redact_pii

def test_content_tokens_empty_string_returns_empty_set():
    assert _content_tokens('') == set()
    assert _content_tokens(None) == set()

def test_content_tokens_none_does_not_include_xxxx_tokens():
    result = _content_tokens(None)
    assert 'xxxx' not in result
    assert result == set()

def test_groundedness_support_rounded_to_4_decimals():
    answer = 'alpha beta gamma delta epsilon zeta eta theta'
    contexts = ['alpha beta gamma']
    result = groundedness(answer, contexts, threshold=0.5)
    expected_support = 3 / 8
    assert result['support'] == pytest.approx(round(expected_support, 4), rel=1e-06)
    assert result['support'] == round(result['support'], 4)

def test_redact_pii_email_exact_replacement():
    text = 'Contact me at john.doe@example.com please'
    result = redact_pii(text)
    assert result == 'Contact me at [redacted-email] please'
    assert 'XX' not in result

def test_redact_pii_ssn_exact_replacement():
    text = 'SSN: 123-45-6789 on file'
    result = redact_pii(text)
    assert result == 'SSN: [redacted-ssn] on file'
    assert 'XX' not in result

def test_redact_pii_phone_exact_replacement():
    text = 'Call 555-123-4567 now'
    result = redact_pii(text)
    assert result == 'Call [redacted-phone] now'
    assert 'XX' not in result

def test_redact_pii_all_types_together_no_extra_markers():
    text = 'Email: alice@test.com, SSN: 987-65-4321, Phone: 555-987-6543, Card: 4111111111111111'
    result = redact_pii(text)
    assert '[redacted-email]' in result
    assert '[redacted-ssn]' in result
    assert '[redacted-phone]' in result
    assert '[redacted-card]' in result
    assert 'XX' not in result
