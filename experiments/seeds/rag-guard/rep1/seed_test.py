import re
import pytest
from rag_guard.guard import should_refuse, groundedness, redact_pii

def test_should_refuse_empty_hits_returns_true():
    assert should_refuse([]) is True

def test_should_refuse_none_like_empty_list_true():
    assert should_refuse([], min_score=0.05) is True

def test_should_refuse_score_above_threshold_false():
    hits = [{'score': 0.5}]
    assert should_refuse(hits, min_score=0.05) is False

def test_should_refuse_score_below_threshold_true():
    hits = [{'score': 0.01}]
    assert should_refuse(hits, min_score=0.05) is True

def test_should_refuse_score_exactly_equal_to_threshold_is_not_refused():
    hits = [{'score': 0.05}]
    assert should_refuse(hits, min_score=0.05) is False

def test_should_refuse_takes_max_over_multiple_hits():
    hits = [{'score': 0.01}, {'score': 0.2}, {'score': 0.03}]
    assert should_refuse(hits, min_score=0.05) is False

def test_should_refuse_missing_score_defaults_to_zero():
    hits = [{}]
    assert should_refuse(hits, min_score=0.05) is True

def test_should_refuse_custom_min_score_higher_threshold():
    hits = [{'score': 0.3}]
    assert should_refuse(hits, min_score=0.5) is True

def test_should_refuse_custom_min_score_lower_threshold():
    hits = [{'score': 0.3}]
    assert should_refuse(hits, min_score=0.1) is False

def test_groundedness_empty_answer_not_grounded():
    result = groundedness('', ['some context here'])
    assert result['grounded'] is False
    assert result['support'] == pytest.approx(0.0)

def test_groundedness_answer_only_stopwords_not_grounded():
    result = groundedness('the and for', ['anything goes here'])
    assert result['grounded'] is False
    assert result['support'] == pytest.approx(0.0)

def test_groundedness_full_support():
    result = groundedness('cats', ['cats are great'])
    assert result['support'] == pytest.approx(1.0)
    assert result['grounded'] is True

def test_groundedness_partial_support_at_threshold():
    result = groundedness('cats dogs', ['cats are here'], threshold=0.5)
    assert result['support'] == pytest.approx(0.5)
    assert result['grounded'] is True

def test_groundedness_partial_support_below_threshold():
    result = groundedness('cats dogs', ['cats are here'], threshold=0.6)
    assert result['support'] == pytest.approx(0.5)
    assert result['grounded'] is False

def test_groundedness_no_support():
    result = groundedness('xyzzy', ['abcdef ghijkl'])
    assert result['support'] == pytest.approx(0.0)
    assert result['grounded'] is False

def test_groundedness_no_context_zero_support():
    result = groundedness('hello world', [])
    assert result['support'] == pytest.approx(0.0)
    assert result['grounded'] is False

def test_groundedness_multiple_contexts_union():
    result = groundedness('hello world', ['hello there', 'world news'])
    assert result['support'] == pytest.approx(1.0)
    assert result['grounded'] is True

def test_groundedness_case_insensitive_tokenization():
    result = groundedness('Hello WORLD', ['hello world'])
    assert result['support'] == pytest.approx(1.0)
    assert result['grounded'] is True

def test_groundedness_support_is_rounded_to_four_decimals():
    result = groundedness('alpha beta gamma', ['alpha only'])
    assert result['support'] == pytest.approx(round(1 / 3, 4), rel=1e-06)

def test_redact_pii_email():
    text = 'Contact me at john.doe@example.com please'
    expected = 'Contact me at [redacted-email] please'
    assert redact_pii(text) == expected

def test_redact_pii_ssn():
    text = 'SSN 123-45-6789 here'
    expected = 'SSN [redacted-ssn] here'
    assert redact_pii(text) == expected

def test_redact_pii_phone_with_dashes():
    text = 'Call 123-456-7890 today'
    expected = 'Call [redacted-phone] today'
    assert redact_pii(text) == expected

def test_redact_pii_phone_with_dots():
    text = 'Call 123.456.7890 today'
    expected = 'Call [redacted-phone] today'
    assert redact_pii(text) == expected

def test_redact_pii_no_pii_unchanged():
    text = 'This is a plain sentence with no sensitive data.'
    assert redact_pii(text) == text

def test_redact_pii_empty_string():
    assert redact_pii('') == ''

def test_redact_pii_multiple_types_combined():
    text = 'Email test@example.com, SSN 123-45-6789, phone 123-456-7890, card 4111111111111111'
    result = redact_pii(text)
    assert '[redacted-email]' in result
    assert '[redacted-ssn]' in result
    assert '[redacted-phone]' in result
    assert '[redacted-card]' in result
    assert 'test@example.com' not in result
    assert '123-45-6789' not in result
    assert '123-456-7890' not in result
    assert '4111111111111111' not in result

def test_redact_pii_short_number_not_treated_as_card():
    text = 'Number 123456789012 is not a card'
    assert redact_pii(text) == text
