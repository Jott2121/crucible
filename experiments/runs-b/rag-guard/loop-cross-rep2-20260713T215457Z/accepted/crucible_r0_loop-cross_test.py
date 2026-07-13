"""Tests for rag_guard.guard: should_refuse, groundedness, redact_pii."""
import pytest

from rag_guard.guard import should_refuse, groundedness, redact_pii


# --------------------------------------------------------------------------
# should_refuse
# --------------------------------------------------------------------------

def test_should_refuse_empty_hits():
    assert should_refuse([]) is True


def test_should_refuse_below_threshold():
    hits = [{"score": 0.01}, {"score": 0.02}]
    assert should_refuse(hits) is True


def test_should_refuse_above_threshold():
    hits = [{"score": 0.5}, {"score": 0.1}]
    assert should_refuse(hits) is False


def test_should_refuse_exactly_at_threshold_not_refused():
    # max score equal to min_score => NOT < min_score => not refused
    hits = [{"score": 0.05}]
    assert should_refuse(hits, min_score=0.05) is False


def test_should_refuse_just_below_threshold():
    hits = [{"score": 0.0499}]
    assert should_refuse(hits, min_score=0.05) is True


def test_should_refuse_missing_score_defaults_to_zero():
    hits = [{"foo": "bar"}]
    # default score 0.0 < default min_score 0.05 -> refuse
    assert should_refuse(hits) is True


def test_should_refuse_missing_score_with_zero_min_score():
    hits = [{"foo": "bar"}]
    # score defaults to 0.0, min_score 0.0 -> 0.0 < 0.0 is False -> not refused
    assert should_refuse(hits, min_score=0.0) is False


def test_should_refuse_custom_min_score():
    hits = [{"score": 0.2}]
    assert should_refuse(hits, min_score=0.3) is True
    assert should_refuse(hits, min_score=0.1) is False


def test_should_refuse_uses_max_of_multiple_hits():
    hits = [{"score": 0.01}, {"score": 0.9}, {"score": 0.02}]
    assert should_refuse(hits, min_score=0.05) is False


# --------------------------------------------------------------------------
# groundedness
# --------------------------------------------------------------------------

def test_groundedness_empty_answer():
    result = groundedness("", ["some context here"])
    assert result == {"grounded": False, "support": 0.0}


def test_groundedness_answer_only_stopwords():
    # "the", "and", "for" are all in the stopword set
    result = groundedness("the and for", ["anything at all"])
    assert result == {"grounded": False, "support": 0.0}


def test_groundedness_answer_only_single_char_tokens():
    # tokens must be at least 2 chars; single letters won't match _TOKEN regex
    result = groundedness("x y z", ["x y z context"])
    assert result == {"grounded": False, "support": 0.0}


def test_groundedness_full_support():
    result = groundedness("cats dogs", ["cats dogs birds live here"])
    assert result["support"] == pytest.approx(1.0, rel=1e-6)
    assert result["grounded"] is True


def test_groundedness_partial_support_below_threshold():
    # ans content tokens: {cats, dogs, birds} (3 tokens)
    # ctx content tokens: {cats, dogs} -> intersection size 2
    result = groundedness("cats dogs birds", ["cats dogs live somewhere"])
    assert result["support"] == pytest.approx(2 / 3, rel=1e-4)
    assert result["grounded"] is True  # 0.667 >= default threshold 0.5


def test_groundedness_partial_support_with_high_threshold():
    result = groundedness("cats dogs birds", ["cats dogs live somewhere"], threshold=0.9)
    assert result["support"] == pytest.approx(2 / 3, rel=1e-4)
    assert result["grounded"] is False


def test_groundedness_no_context_gives_zero_support():
    result = groundedness("cats dogs birds", [])
    assert result["support"] == pytest.approx(0.0, abs=1e-9)
    assert result["grounded"] is False


def test_groundedness_no_overlap():
    result = groundedness("elephants giraffes", ["cats dogs birds"])
    assert result["support"] == pytest.approx(0.0, abs=1e-9)
    assert result["grounded"] is False


def test_groundedness_multiple_contexts_merged():
    # ans tokens: {alpha, beta, gamma}
    # context 1 has alpha, context 2 has beta -> union covers 2 of 3
    result = groundedness("alpha beta gamma", ["alpha only", "beta only"])
    assert result["support"] == pytest.approx(2 / 3, rel=1e-4)


def test_groundedness_threshold_boundary_equal():
    # support exactly equal to threshold should be grounded (>= comparison)
    result = groundedness("alpha beta", ["alpha context"], threshold=0.5)
    assert result["support"] == pytest.approx(0.5, rel=1e-6)
    assert result["grounded"] is True


# --------------------------------------------------------------------------
# redact_pii
# --------------------------------------------------------------------------

def test_redact_pii_no_pii_unchanged():
    text = "Hello world, this is a normal sentence."
    assert redact_pii(text) == text


def test_redact_pii_email():
    text = "Contact me at john.doe@example.com for details."
    result = redact_pii(text)
    assert "[redacted-email]" in result
    assert "john.doe@example.com" not in result


def test_redact_pii_phone_dash_format():
    text = "Call 555-123-4567 now."
    result = redact_pii(text)
    assert "[redacted-phone]" in result
    assert "555-123-4567" not in result


def test_redact_pii_phone_dot_format():
    text = "Call 555.123.4567 now."
    result = redact_pii(text)
    assert "[redacted-phone]" in result


def test_redact_pii_phone_space_format():
    text = "Call 555 123 4567 now."
    result = redact_pii(text)
    assert "[redacted-phone]" in result


def test_redact_pii_ssn():
    text = "SSN: 123-45-6789 on file."
    result = redact_pii(text)
    assert "[redacted-ssn]" in result
    assert "123-45-6789" not in result


def test_redact_pii_card_number_16_digits():
    text = "Card number 4111111111111111 was used."
    result = redact_pii(text)
    assert "[redacted-card]" in result
    assert "4111111111111111" not in result


def test_redact_pii_card_number_with_spaces():
    text = "Card 4111 1111 1111 1111 was charged."
    result = redact_pii(text)
    assert "[redacted-card]" in result


def test_redact_pii_short_digit_sequence_not_redacted_as_card():
    # 12 digits is below the 13-16 range required for card matching
    text = "Reference number 123456789012 is not a card."
    result = redact_pii(text)
    assert "123456789012" in result
    assert "[redacted-card]" not in result


def test_redact_pii_combined_email_and_ssn():
    text = "Email jane@example.com, SSN 987-65-4321."
    result = redact_pii(text)
    assert "[redacted-email]" in result
    assert "[redacted-ssn]" in result
    assert "jane@example.com" not in result
    assert "987-65-4321" not in result


def test_redact_pii_combined_all_types():
    text = (
        "Email: a@b.com, Phone: 555-111-2222, "
        "SSN: 111-22-3333, Card: 4111111111111111"
    )
    result = redact_pii(text)
    assert "[redacted-email]" in result
    assert "[redacted-ssn]" in result
    assert "[redacted-card]" in result
    assert "a@b.com" not in result
    assert "111-22-3333" not in result
    assert "4111111111111111" not in result


def test_redact_pii_empty_string():
    assert redact_pii("") == ""

