import pytest

from rag_guard.guard import should_refuse, groundedness, redact_pii


# ---------------------------------------------------------------------------
# should_refuse
# ---------------------------------------------------------------------------

def test_should_refuse_empty_hits():
    assert should_refuse([]) is True


def test_should_refuse_below_default_threshold():
    hits = [{"score": 0.04}]
    assert should_refuse(hits) is True


def test_should_refuse_exactly_at_threshold_not_refused():
    # max_score == min_score -> not strictly less than -> should NOT refuse
    hits = [{"score": 0.05}]
    assert should_refuse(hits) is False


def test_should_refuse_above_threshold():
    hits = [{"score": 0.1}, {"score": 0.02}]
    assert should_refuse(hits) is False


def test_should_refuse_missing_score_defaults_to_zero():
    hits = [{}]
    assert should_refuse(hits) is True


def test_should_refuse_negative_score():
    hits = [{"score": -1.0}]
    assert should_refuse(hits) is True


def test_should_refuse_custom_min_score():
    hits = [{"score": 0.2}]
    assert should_refuse(hits, min_score=0.3) is True
    assert should_refuse(hits, min_score=0.1) is False


def test_should_refuse_multiple_hits_takes_max():
    hits = [{"score": 0.01}, {"score": 0.02}, {"score": 0.5}]
    assert should_refuse(hits, min_score=0.4) is False
    assert should_refuse(hits, min_score=0.6) is True


# ---------------------------------------------------------------------------
# groundedness
# ---------------------------------------------------------------------------

def test_groundedness_empty_answer():
    result = groundedness("", ["some context here"])
    assert result["grounded"] is False
    assert result["support"] == pytest.approx(0.0)


def test_groundedness_answer_all_stopwords():
    # "the", "and", "for" are all stopwords -> no content tokens
    result = groundedness("the and for", ["the and for are here"])
    assert result["grounded"] is False
    assert result["support"] == pytest.approx(0.0)


def test_groundedness_fully_supported():
    result = groundedness("Python", ["Python is great"])
    assert result["support"] == pytest.approx(1.0)
    assert result["grounded"] is True


def test_groundedness_half_supported_meets_default_threshold():
    result = groundedness("cats dogs", ["cats are cute"])
    assert result["support"] == pytest.approx(0.5)
    assert result["grounded"] is True  # 0.5 >= 0.5 threshold


def test_groundedness_partial_support_below_threshold():
    result = groundedness("cats dogs birds", ["cats are cute"])
    assert result["support"] == pytest.approx(0.3333, rel=1e-3)
    assert result["grounded"] is False


def test_groundedness_custom_threshold_allows_partial_support():
    result = groundedness("cats dogs birds", ["cats are cute"], threshold=0.3)
    assert result["support"] == pytest.approx(0.3333, rel=1e-3)
    assert result["grounded"] is True


def test_groundedness_no_context_gives_zero_support():
    result = groundedness("hello world", [])
    assert result["support"] == pytest.approx(0.0)
    assert result["grounded"] is False


def test_groundedness_multiple_contexts_union():
    result = groundedness("cats dogs", ["cats are here", "dogs are here too"])
    assert result["support"] == pytest.approx(1.0)
    assert result["grounded"] is True


def test_groundedness_support_rounded_to_four_decimals():
    result = groundedness("one two three", ["one context word"])
    # ans tokens: {"one", "two", "three"}; ctx tokens from "one context word":
    # {"one", "context", "word"}; intersection = {"one"} -> support = 1/3
    assert result["support"] == pytest.approx(round(1 / 3, 4))


# ---------------------------------------------------------------------------
# redact_pii
# ---------------------------------------------------------------------------

def test_redact_pii_email():
    text = "Contact me at test.user+tag@sub.example.com today"
    result = redact_pii(text)
    assert "[redacted-email]" in result
    assert "test.user+tag@sub.example.com" not in result


def test_redact_pii_ssn():
    text = "SSN: 123-45-6789 recorded"
    result = redact_pii(text)
    assert result == "SSN: [redacted-ssn] recorded"


def test_redact_pii_phone_with_dashes():
    text = "Call 555-867-5309 now"
    result = redact_pii(text)
    assert result == "Call [redacted-phone] now"


def test_redact_pii_phone_with_dots():
    text = "Call 555.867.5309 now"
    result = redact_pii(text)
    assert result == "Call [redacted-phone] now"


def test_redact_pii_card_number_no_separators():
    text = "4111111111111111"
    result = redact_pii(text)
    assert result == "[redacted-card]"


def test_redact_pii_card_number_with_spaces():
    text = "4111 1111 1111 1111"
    result = redact_pii(text)
    assert result == "[redacted-card]"


def test_redact_pii_no_pii_unchanged():
    text = "This is a plain sentence with no sensitive data."
    result = redact_pii(text)
    assert result == text


def test_redact_pii_short_number_not_redacted():
    text = "The code is 1234"
    result = redact_pii(text)
    assert result == "The code is 1234"


def test_redact_pii_combined_email_and_phone():
    text = "Reach me at john@example.com or 555-123-4567."
    result = redact_pii(text)
    assert "[redacted-email]" in result
    assert "[redacted-phone]" in result
    assert "john@example.com" not in result
    assert "555-123-4567" not in result


def test_redact_pii_ssn_not_confused_with_phone_pattern():
    # SSN pattern (3-2-4) should be redacted as ssn, not phone
    text = "123-45-6789"
    result = redact_pii(text)
    assert result == "[redacted-ssn]"
