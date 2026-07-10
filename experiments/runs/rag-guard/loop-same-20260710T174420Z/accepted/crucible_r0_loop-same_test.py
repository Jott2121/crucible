import pytest
from rag_guard.guard import should_refuse, groundedness, redact_pii

def test_should_refuse_empty_hits():
    assert should_refuse([]) is True

def test_should_refuse_below_default_threshold():
    hits = [{'score': 0.01}, {'score': 0.02}]
    assert should_refuse(hits) is True

def test_should_refuse_at_default_threshold_boundary_not_refused():
    hits = [{'score': 0.05}]
    assert should_refuse(hits) is False

def test_should_refuse_above_default_threshold():
    hits = [{'score': 0.9}]
    assert should_refuse(hits) is False

def test_should_refuse_uses_max_score_among_hits():
    hits = [{'score': 0.01}, {'score': 0.5}, {'score': 0.02}]
    assert should_refuse(hits) is False

def test_should_refuse_missing_score_key_defaults_to_zero():
    hits = [{'foo': 'bar'}]
    assert should_refuse(hits) is True

def test_should_refuse_custom_min_score():
    hits = [{'score': 0.2}]
    assert should_refuse(hits, min_score=0.3) is True
    assert should_refuse(hits, min_score=0.1) is False

def test_should_refuse_custom_min_score_boundary():
    hits = [{'score': 0.3}]
    assert should_refuse(hits, min_score=0.3) is False

def test_groundedness_empty_answer():
    result = groundedness('', ['some context here'])
    assert result['grounded'] is False
    assert result['support'] == pytest.approx(0.0)

def test_groundedness_answer_only_stopwords():
    result = groundedness('the and for are', ['anything at all'])
    assert result['grounded'] is False
    assert result['support'] == pytest.approx(0.0)

def test_groundedness_fully_supported():
    result = groundedness('apple banana cherry', ['apple banana cherry smoothie'])
    assert result['support'] == pytest.approx(1.0)
    assert result['grounded'] is True

def test_groundedness_exact_half_boundary_is_grounded():
    result = groundedness('apple banana', ['apple'])
    assert result['support'] == pytest.approx(0.5)
    assert result['grounded'] is True

def test_groundedness_no_support_at_all():
    result = groundedness('apple banana', ['zebra octopus'])
    assert result['support'] == pytest.approx(0.0)
    assert result['grounded'] is False

def test_groundedness_multiple_contexts_union():
    result = groundedness('apple banana', ['apple only', 'banana only'])
    assert result['support'] == pytest.approx(1.0)
    assert result['grounded'] is True

def test_groundedness_case_insensitive_matching():
    result = groundedness('APPLE Banana', ['apple banana'])
    assert result['support'] == pytest.approx(1.0)
    assert result['grounded'] is True

def test_redact_pii_no_pii_unchanged():
    text = 'This is a plain sentence with no sensitive data.'
    assert redact_pii(text) == text

def test_redact_pii_email():
    text = 'Contact me at foo.bar@example.com for details.'
    result = redact_pii(text)
    assert 'foo.bar@example.com' not in result
    assert '[redacted-email]' in result
    assert result == 'Contact me at [redacted-email] for details.'

def test_redact_pii_multiple_emails():
    text = 'email1@test.com and email2@test.org'
    result = redact_pii(text)
    assert result == '[redacted-email] and [redacted-email]'

def test_redact_pii_ssn():
    text = 'SSN: 123-45-6789 on file.'
    result = redact_pii(text)
    assert result == 'SSN: [redacted-ssn] on file.'

def test_redact_pii_phone_with_dashes():
    text = 'Call 123-456-7890 now.'
    result = redact_pii(text)
    assert result == 'Call [redacted-phone] now.'

def test_redact_pii_phone_with_dots():
    text = 'Call 123.456.7890 now.'
    result = redact_pii(text)
    assert result == 'Call [redacted-phone] now.'

def test_redact_pii_phone_with_spaces():
    text = 'Call 123 456 7890 now.'
    result = redact_pii(text)
    assert result == 'Call [redacted-phone] now.'

def test_redact_pii_card_number_no_separators():
    text = 'Card 4111111111111111 expires soon.'
    result = redact_pii(text)
    assert '4111111111111111' not in result
    assert '[redacted-card]' in result

def test_redact_pii_card_number_with_dashes():
    text = 'Card 4111-1111-1111-1111 expires soon.'
    result = redact_pii(text)
    assert '[redacted-card]' in result
    assert '4111-1111-1111-1111' not in result

def test_redact_pii_short_digit_run_not_redacted_as_card():
    text = 'Ref number 411111111111 done.'
    result = redact_pii(text)
    assert result == text

def test_redact_pii_seventeen_digit_run_not_matched_as_card():
    text = 'Ref number 41111111111111111 done.'
    result = redact_pii(text)
    assert result == text

def test_redact_pii_combined_types_in_one_text():
    text = 'Email: a@b.com, SSN: 123-45-6789, Phone: 123-456-7890, Card: 4111111111111111.'
    result = redact_pii(text)
    assert 'a@b.com' not in result
    assert '123-45-6789' not in result
    assert '123-456-7890' not in result
    assert '4111111111111111' not in result
    assert '[redacted-email]' in result
    assert '[redacted-ssn]' in result
    assert '[redacted-phone]' in result
    assert '[redacted-card]' in result
