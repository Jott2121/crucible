import pytest

from rag_guard.guard import should_refuse, groundedness, redact_pii


# ---------------------------------------------------------------------------
# should_refuse
# ---------------------------------------------------------------------------

def test_should_refuse_empty_hits():
    assert should_refuse([]) is True


def test_should_refuse_below_min_score_default():
    hits = [{"score": 0.01}, {"score": 0.02}]
    assert should_refuse(hits) is True


def test_should_refuse_above_min_score_default():
    hits = [{"score": 0.01}, {"score": 0.9}]
    assert should_refuse(hits) is False


def test_should_refuse_score_equal_to_min_score_is_not_refused():
    # condition is strictly `<`, so equality should NOT trigger refusal
    hits = [{"score": 0.05}]
    assert should_refuse(hits, min_score=0.05) is False


def test_should_refuse_missing_score_defaults_to_zero():
    hits = [{"foo": "bar"}]
    assert should_refuse(hits) is True


def test_should_refuse_custom_min_score():
    hits = [{"score": 0.3}]
    assert should_refuse(hits, min_score=0.5) is True
    assert should_refuse(hits, min_score=0.2) is False


# ---------------------------------------------------------------------------
# groundedness
# ---------------------------------------------------------------------------

def test_groundedness_empty_answer():
    result = groundedness("", ["some context here"])
    assert result == {"grounded": False, "support": 0.0}


def test_groundedness_answer_only_stopwords():
    # "the", "and", "for" are all stopwords -> no content tokens
    result = groundedness("the and for", ["anything at all"])
    assert result == {"grounded": False, "support": 0.0}


def test_groundedness_fully_supported():
    answer = "shipping delivery arrives quickly"
    contexts = ["shipping delivery arrives quickly information"]
    result = groundedness(answer, contexts)
    assert result["support"] == pytest.approx(1.0, rel=1e-6)
    assert result["grounded"] is True


def test_groundedness_no_overlap():
    answer = "alpha beta gamma delta"
    contexts = ["nothing matches here whatsoever"]
    result = groundedness(answer, contexts)
    assert result["support"] == pytest.approx(0.0, rel=1e-6)
    assert result["grounded"] is False


def test_groundedness_partial_support_half():
    # answer content tokens: shipping, delivery, arrives, quickly (4 distinct)
    # context content tokens: shipping, delivery, information
    # intersection: shipping, delivery -> 2/4 = 0.5
    answer = "shipping delivery arrives quickly"
    contexts = ["shipping delivery information"]
    result = groundedness(answer, contexts, threshold=0.5)
    assert result["support"] == pytest.approx(0.5, rel=1e-6)
    assert result["grounded"] is True  # threshold comparison is >=


def test_groundedness_partial_support_below_threshold():
    answer = "shipping delivery arrives quickly"
    contexts = ["shipping delivery information"]
    result = groundedness(answer, contexts, threshold=0.6)
    assert result["support"] == pytest.approx(0.5, rel=1e-6)
    assert result["grounded"] is False


def test_groundedness_empty_contexts_list():
    answer = "shipping delivery"
    result = groundedness(answer, [])
    assert result["support"] == pytest.approx(0.0, rel=1e-6)
    assert result["grounded"] is False


def test_groundedness_multiple_contexts_union():
    # content tokens split across two context strings
    answer = "shipping delivery arrives"
    contexts = ["shipping info", "delivery arrives soon"]
    result = groundedness(answer, contexts)
    assert result["support"] == pytest.approx(1.0, rel=1e-6)
    assert result["grounded"] is True


# ---------------------------------------------------------------------------
# redact_pii
# ---------------------------------------------------------------------------

def test_redact_pii_email():
    text = "Contact us at john.doe@example.com for details."
    result = redact_pii(text)
    assert "[redacted-email]" in result
    assert "john.doe@example.com" not in result


def test_redact_pii_phone_with_dashes():
    text = "Call 123-456-7890 now."
    result = redact_pii(text)
    assert "[redacted-phone]" in result
    assert "123-456-7890" not in result


def test_redact_pii_phone_with_dots():
    text = "Call 123.456.7890 now."
    result = redact_pii(text)
    assert "[redacted-phone]" in result
    assert "123.456.7890" not in result


def test_redact_pii_ssn():
    text = "SSN: 123-45-6789 on file."
    result = redact_pii(text)
    assert "[redacted-ssn]" in result
    assert "123-45-6789" not in result


def test_redact_pii_card_number_no_separators():
    text = "Card number: 4111111111111111 expires soon."
    result = redact_pii(text)
    assert "[redacted-card]" in result
    assert "4111111111111111" not in result


def test_redact_pii_card_number_with_spaces():
    text = "Card number: 4111 1111 1111 1111 expires soon."
    result = redact_pii(text)
    assert "[redacted-card]" in result
    assert "4111 1111 1111 1111" not in result


def test_redact_pii_no_pii_unchanged():
    text = "This is a plain sentence with no sensitive data."
    result = redact_pii(text)
    assert result == text


def test_redact_pii_multiple_types_combined():
    text = "Email me at foo@bar.com or call 111-222-3333, SSN 987-65-4321."
    result = redact_pii(text)
    assert "[redacted-email]" in result
    assert "[redacted-phone]" in result
    assert "[redacted-ssn]" in result
    assert "foo@bar.com" not in result
    assert "111-222-3333" not in result
    assert "987-65-4321" not in result
