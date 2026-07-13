import pytest
from rag_guard.guard import should_refuse, groundedness, redact_pii

def test_should_refuse_empty_hits():
    assert should_refuse([]) is True

def test_should_refuse_below_default_threshold():
    assert should_refuse([{'score': 0.03}]) is True

def test_should_refuse_exactly_at_default_threshold_not_refused():
    assert should_refuse([{'score': 0.05}]) is False

def test_should_refuse_above_default_threshold():
    assert should_refuse([{'score': 0.1}]) is False

def test_should_refuse_uses_max_score_among_hits():
    hits = [{'score': 0.1}, {'score': 0.02}]
    assert should_refuse(hits) is False

def test_should_refuse_missing_score_key_defaults_to_zero():
    hits = [{'no_score_key': 1}]
    assert should_refuse(hits) is True

def test_should_refuse_custom_min_score_below():
    assert should_refuse([{'score': 0.2}], min_score=0.3) is True

def test_should_refuse_custom_min_score_equal():
    assert should_refuse([{'score': 0.3}], min_score=0.3) is False

def test_should_refuse_custom_min_score_above():
    assert should_refuse([{'score': 0.35}], min_score=0.3) is False

def test_groundedness_empty_answer():
    result = groundedness('', ['some context here'])
    assert result['grounded'] is False
    assert result['support'] == pytest.approx(0.0)

def test_groundedness_answer_all_stopwords_no_content_tokens():
    result = groundedness('and or the', ['anything at all'])
    assert result['grounded'] is False
    assert result['support'] == pytest.approx(0.0)

def test_groundedness_full_support():
    result = groundedness('apple banana', ['apple banana available now'])
    assert result['grounded'] is True
    assert result['support'] == pytest.approx(1.0)

def test_groundedness_zero_support():
    result = groundedness('apple banana', ['completely unrelated words here'])
    assert result['grounded'] is False
    assert result['support'] == pytest.approx(0.0)

def test_groundedness_exactly_at_default_threshold_is_grounded():
    result = groundedness('cats dogs', ['dogs are great'])
    assert result['support'] == pytest.approx(0.5, rel=1e-06)
    assert result['grounded'] is True

def test_groundedness_custom_threshold_above_support_not_grounded():
    result = groundedness('cats dogs', ['dogs are great'], threshold=0.6)
    assert result['support'] == pytest.approx(0.5, rel=1e-06)
    assert result['grounded'] is False

def test_groundedness_stopwords_filtered_from_context_too():
    result = groundedness('Shipping takes 5 business days', ['Our shipping process is fast'])
    assert result['support'] == pytest.approx(1.0)
    assert result['grounded'] is True

def test_groundedness_empty_contexts_list():
    result = groundedness('apple banana', [])
    assert result['support'] == pytest.approx(0.0)
    assert result['grounded'] is False

def test_redact_pii_email():
    assert redact_pii('Email: alice@example.com') == 'Email: [redacted-email]'

def test_redact_pii_ssn():
    assert redact_pii('SSN 123-45-6789') == 'SSN [redacted-ssn]'

def test_redact_pii_phone_with_dashes():
    assert redact_pii('Call 123-456-7890 now') == 'Call [redacted-phone] now'

def test_redact_pii_phone_with_dots():
    assert redact_pii('Call 123.456.7890 now') == 'Call [redacted-phone] now'

def test_redact_pii_phone_with_spaces():
    assert redact_pii('Call 123 456 7890 now') == 'Call [redacted-phone] now'

def test_redact_pii_no_pii_unchanged():
    text = 'Hello world, nothing sensitive here.'
    assert redact_pii(text) == text

def test_redact_pii_multiple_types_combined():
    text = 'Contact alice@example.com or call 123-456-7890. SSN: 123-45-6789.'
    expected = 'Contact [redacted-email] or call [redacted-phone]. SSN: [redacted-ssn].'
    assert redact_pii(text) == expected

def test_redact_pii_short_digit_sequence_not_redacted_as_card():
    text = 'code 123456789012 end'
    assert redact_pii(text) == text

