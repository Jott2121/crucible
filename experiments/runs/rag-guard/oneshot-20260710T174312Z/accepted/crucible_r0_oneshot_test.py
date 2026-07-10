"""Tests for rag_guard.guard: should_refuse, groundedness, redact_pii."""
import pytest
from rag_guard.guard import should_refuse, groundedness, redact_pii

def test_should_refuse_empty_hits():
    assert should_refuse([]) is True

def test_should_refuse_score_below_default_threshold():
    assert should_refuse([{'score': 0.01}]) is True

def test_should_refuse_score_above_default_threshold():
    assert should_refuse([{'score': 0.1}]) is False

def test_should_refuse_score_exactly_at_default_threshold_is_not_refused():
    assert should_refuse([{'score': 0.05}]) is False

def test_should_refuse_score_just_below_default_threshold_is_refused():
    assert should_refuse([{'score': 0.0499}]) is True

def test_should_refuse_uses_max_score_among_hits():
    hits = [{'score': 0.01}, {'score': 0.2}, {'score': 0.0}]
    assert should_refuse(hits) is False

def test_should_refuse_missing_score_defaults_to_zero():
    assert should_refuse([{}]) is True

def test_should_refuse_mixed_missing_and_present_scores():
    hits = [{}, {'score': 0.2}]
    assert should_refuse(hits) is False

def test_should_refuse_custom_min_score_refuses_higher_bar():
    assert should_refuse([{'score': 0.3}], min_score=0.5) is True

def test_should_refuse_custom_min_score_allows_when_met():
    assert should_refuse([{'score': 0.6}], min_score=0.5) is False

def test_groundedness_empty_answer_returns_zero_support():
    result = groundedness('', ['some context here'])
    assert result['grounded'] is False
    assert result['support'] == pytest.approx(0.0)

def test_groundedness_answer_all_stopwords_returns_zero_support():
    result = groundedness('the and for', ['cat dog fish'])
    assert result['grounded'] is False
    assert result['support'] == pytest.approx(0.0)

def test_groundedness_fully_supported_answer():
    answer = 'Python is great'
    contexts = ['Python is a great language']
    result = groundedness(answer, contexts)
    assert result['support'] == pytest.approx(1.0)
    assert result['grounded'] is True

def test_groundedness_partially_supported_answer_below_threshold():
    answer = 'Python is really great and awesome'
    contexts = ['Python is fantastic']
    result = groundedness(answer, contexts)
    assert result['support'] == pytest.approx(0.25, rel=1e-06)
    assert result['grounded'] is False

def test_groundedness_partially_supported_answer_at_custom_threshold():
    answer = 'Python is really great and awesome'
    contexts = ['Python is fantastic']
    result = groundedness(answer, contexts, threshold=0.25)
    assert result['support'] == pytest.approx(0.25, rel=1e-06)
    assert result['grounded'] is True

def test_groundedness_rounding_to_four_decimals():
    answer = 'cat dog fish'
    contexts = ['cat only']
    result = groundedness(answer, contexts)
    assert result['support'] == pytest.approx(0.3333, abs=0.0001)
    assert result['grounded'] is False

def test_groundedness_empty_contexts_list():
    result = groundedness('cat', [])
    assert result['support'] == pytest.approx(0.0)
    assert result['grounded'] is False

def test_groundedness_multiple_contexts_are_unioned():
    answer = 'cat dog'
    contexts = ['cat appears here', 'dog appears elsewhere']
    result = groundedness(answer, contexts)
    assert result['support'] == pytest.approx(1.0)
    assert result['grounded'] is True

def test_redact_pii_email():
    text = 'Reach me at jane.doe@example.com please'
    assert redact_pii(text) == 'Reach me at [redacted-email] please'

def test_redact_pii_ssn():
    text = 'SSN: 123-45-6789 done'
    assert redact_pii(text) == 'SSN: [redacted-ssn] done'

def test_redact_pii_phone_with_dashes():
    text = 'Call 123-456-7890 now'
    assert redact_pii(text) == 'Call [redacted-phone] now'

def test_redact_pii_phone_with_dots():
    text = 'Call 123.456.7890 now'
    assert redact_pii(text) == 'Call [redacted-phone] now'

def test_redact_pii_phone_with_spaces():
    text = 'Call 123 456 7890 now'
    assert redact_pii(text) == 'Call [redacted-phone] now'

def test_redact_pii_combined_all_types():
    text = 'Email alice@example.com SSN 123-45-6789 Phone 555-123-4567 Card 4012888888881881'
    expected = 'Email [redacted-email] SSN [redacted-ssn] Phone [redacted-phone] Card [redacted-card]'
    assert redact_pii(text) == expected

def test_redact_pii_leaves_non_pii_text_unchanged():
    text = 'Our support hours are 9 to 5'
    assert redact_pii(text) == 'Our support hours are 9 to 5'

def test_redact_pii_empty_string():
    assert redact_pii('') == ''
