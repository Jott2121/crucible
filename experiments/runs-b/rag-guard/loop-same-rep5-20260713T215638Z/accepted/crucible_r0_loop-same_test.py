import pytest

from rag_guard.guard import should_refuse, groundedness, redact_pii


# ---------------------------------------------------------------------------
# should_refuse
# ---------------------------------------------------------------------------

def test_should_refuse_empty_hits():
    assert should_refuse([]) is True


def test_should_refuse_score_below_default_threshold():
    hits = [{"score": 0.03}]
    assert should_refuse(hits) is True


def test_should_refuse_score_exactly_at_default_threshold_not_refused():
    # 0.05 < 0.05 is False -> should not refuse
    hits = [{"score": 0.05}]
    assert should_refuse(hits) is False


def test_should_refuse_score_above_default_threshold():
    hits = [{"score": 0.10}]
    assert should_refuse(hits) is False


def test_should_refuse_uses_max_score_among_hits():
    hits = [{"score": 0.01}, {"score": 0.2}, {"score": 0.02}]
    assert should_refuse(hits) is False


def test_should_refuse_missing_score_defaults_to_zero():
    hits = [{}]
    assert should_refuse(hits) is True


def test_should_refuse_custom_min_score_refused():
    hits = [{"score": 0.4}]
    assert should_refuse(hits, min_score=0.5) is True


def test_should_refuse_custom_min_score_not_refused():
    hits = [{"score": 0.6}]
    assert should_refuse(hits, min_score=0.5) is False


# ---------------------------------------------------------------------------
# groundedness
# ---------------------------------------------------------------------------

def test_groundedness_empty_answer():
    result = groundedness("", ["some context here"])
    assert result["grounded"] is False
    assert result["support"] == pytest.approx(0.0)


def test_groundedness_answer_only_stopwords():
    # "the", "and", "for" are all in the stopword list -> no content tokens
    result = groundedness("the and for", ["irrelevant context words"])
    assert result["grounded"] is False
    assert result["support"] == pytest.approx(0.0)


def test_groundedness_no_overlap_with_context():
    answer = "Rockets zoom fast"
    contexts = ["The cat sat on the mat"]
    result = groundedness(answer, contexts)
    assert result["support"] == pytest.approx(0.0)
    assert result["grounded"] is False


def test_groundedness_empty_contexts_list():
    answer = "Rockets zoom fast"
    result = groundedness(answer, [])
    assert result["support"] == pytest.approx(0.0)
    assert result["grounded"] is False


def test_groundedness_partial_support_exact_fraction():
    # ans content tokens: widgets, cost, twenty, dollars, each (5 tokens)
    answer = "Widgets cost twenty dollars each"
    # ctx content tokens (after stopword removal): cost, twenty, dollars, premium, widgets
    contexts = ["The cost is twenty dollars for premium widgets"]
    result = groundedness(answer, contexts)
    # intersection: widgets, cost, twenty, dollars -> 4 of 5
    assert result["support"] == pytest.approx(0.8, rel=1e-6)
    assert result["grounded"] is True  # 0.8 >= default threshold 0.5


def test_groundedness_full_support():
    answer = "alpha bravo"
    contexts = ["alpha bravo charlie delta"]
    result = groundedness(answer, contexts)
    assert result["support"] == pytest.approx(1.0, rel=1e-6)
    assert result["grounded"] is True


def test_groundedness_rounding_to_four_decimals():
    # ans tokens: alpha, bravo, charlie (3 tokens), only 1 overlaps context
    answer = "alpha bravo charlie"
    contexts = ["alpha only"]
    result = groundedness(answer, contexts)
    assert result["support"] == pytest.approx(0.3333, rel=1e-4)
    assert result["grounded"] is False  # 0.3333 < 0.5


def test_groundedness_threshold_boundary_inclusive():
    # support will be exactly 0.8, threshold set to 0.8 -> grounded True (>=)
    answer = "Widgets cost twenty dollars each"
    contexts = ["The cost is twenty dollars for premium widgets"]
    result = groundedness(answer, contexts, threshold=0.8)
    assert result["support"] == pytest.approx(0.8, rel=1e-6)
    assert result["grounded"] is True


def test_groundedness_threshold_just_above_support_not_grounded():
    answer = "Widgets cost twenty dollars each"
    contexts = ["The cost is twenty dollars for premium widgets"]
    result = groundedness(answer, contexts, threshold=0.81)
    assert result["support"] == pytest.approx(0.8, rel=1e-6)
    assert result["grounded"] is False


# ---------------------------------------------------------------------------
# redact_pii
# ---------------------------------------------------------------------------

def test_redact_pii_email():
    text = "Contact me at john.doe@example.com for details"
    result = redact_pii(text)
    assert "[redacted-email]" in result
    assert "john.doe@example.com" not in result


def test_redact_pii_multiple_emails():
    text = "Emails: alice@example.com and bob@example.org"
    result = redact_pii(text)
    assert result.count("[redacted-email]") == 2
    assert "alice@example.com" not in result
    assert "bob@example.org" not in result


def test_redact_pii_phone_dash_format():
    text = "Call me at 123-456-7890 today"
    result = redact_pii(text)
    assert "[redacted-phone]" in result
    assert "123-456-7890" not in result


def test_redact_pii_phone_dot_format():
    text = "Call me at 123.456.7890 today"
    result = redact_pii(text)
    assert "[redacted-phone]" in result
    assert "123.456.7890" not in result


def test_redact_pii_phone_space_format():
    text = "Call me at 123 456 7890 today"
    result = redact_pii(text)
    assert "[redacted-phone]" in result
    assert "123 456 7890" not in result


def test_redact_pii_ssn():
    text = "SSN on file: 123-45-6789"
    result = redact_pii(text)
    assert "[redacted-ssn]" in result
    assert "123-45-6789" not in result


def test_redact_pii_card_number():
    text = "Card number: 4111111111111111 expires soon"
    result = redact_pii(text)
    assert "[redacted-card]" in result
    assert "4111111111111111" not in result


def test_redact_pii_combined_all_types():
    text = (
        "Email: jane@example.com, Phone: 555-123-4567, "
        "SSN: 987-65-4321, Card: 4111111111111111"
    )
    result = redact_pii(text)
    assert "[redacted-email]" in result
    assert "[redacted-phone]" in result
    assert "[redacted-ssn]" in result
    assert "[redacted-card]" in result
    assert "jane@example.com" not in result
    assert "555-123-4567" not in result
    assert "987-65-4321" not in result
    assert "4111111111111111" not in result


def test_redact_pii_no_pii_unchanged():
    text = "This is a plain sentence with no sensitive information at all."
    result = redact_pii(text)
    assert result == text


def test_redact_pii_empty_string():
    assert redact_pii("") == ""

