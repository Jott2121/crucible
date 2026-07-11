import pytest
from rag_guard.guard import should_refuse, groundedness, redact_pii


# ---------------------------------------------------------------------------
# should_refuse
# ---------------------------------------------------------------------------

def test_should_refuse_empty_hits():
    assert should_refuse([]) is True


def test_should_refuse_none_like_empty_list():
    assert should_refuse([], min_score=0.0) is True


def test_should_refuse_high_score_does_not_refuse():
    hits = [{"score": 0.9}]
    assert should_refuse(hits) is False


def test_should_refuse_low_score_refuses():
    hits = [{"score": 0.01}]
    assert should_refuse(hits) is True


def test_should_refuse_boundary_equal_min_score_not_refused():
    # max_score < min_score triggers refusal; equal should NOT refuse
    hits = [{"score": 0.05}]
    assert should_refuse(hits, min_score=0.05) is False


def test_should_refuse_boundary_just_below_min_score_refused():
    hits = [{"score": 0.0499}]
    assert should_refuse(hits, min_score=0.05) is True


def test_should_refuse_uses_max_of_multiple_hits():
    hits = [{"score": 0.01}, {"score": 0.5}, {"score": 0.02}]
    assert should_refuse(hits) is False


def test_should_refuse_missing_score_defaults_to_zero():
    hits = [{}]
    assert should_refuse(hits) is True


def test_should_refuse_custom_min_score_threshold():
    hits = [{"score": 0.2}]
    assert should_refuse(hits, min_score=0.3) is True
    assert should_refuse(hits, min_score=0.1) is False


# ---------------------------------------------------------------------------
# groundedness
# ---------------------------------------------------------------------------

def test_groundedness_empty_answer():
    result = groundedness("", ["some context here"])
    assert result == {"grounded": False, "support": 0.0}


def test_groundedness_answer_only_stopwords():
    # "the and for" tokens are all stopwords -> ans set empty
    result = groundedness("the and for", ["anything goes here"])
    assert result == {"grounded": False, "support": 0.0}


def test_groundedness_fully_supported():
    result = groundedness("apple banana cherry", ["apple banana cherry pie"])
    assert result["grounded"] is True
    assert result["support"] == pytest.approx(1.0, rel=1e-6)


def test_groundedness_partial_support_below_default_threshold():
    result = groundedness("apple banana cherry", ["apple only here"])
    assert result["support"] == pytest.approx(1 / 3, rel=1e-4)
    assert result["grounded"] is False


def test_groundedness_partial_support_meets_custom_threshold():
    result = groundedness("apple banana cherry", ["apple only here"], threshold=0.3)
    assert result["support"] == pytest.approx(1 / 3, rel=1e-4)
    assert result["grounded"] is True


def test_groundedness_no_overlap_zero_support():
    result = groundedness("zebra giraffe", ["completely unrelated words"])
    assert result["support"] == pytest.approx(0.0, abs=1e-9)
    assert result["grounded"] is False


def test_groundedness_multiple_contexts_combined():
    result = groundedness(
        "apple banana cherry",
        ["apple appears here", "banana appears there"],
    )
    assert result["support"] == pytest.approx(2 / 3, rel=1e-4)
    assert result["grounded"] is True


def test_groundedness_support_rounded_to_four_decimals():
    result = groundedness("apple banana cherry", ["apple only here"])
    # round(1/3, 4) == 0.3333
    assert result["support"] == pytest.approx(0.3333, abs=1e-4)


def test_groundedness_boundary_support_equals_threshold():
    # single content word fully supported -> support == 1.0, threshold 1.0
    result = groundedness("apple", ["apple"], threshold=1.0)
    assert result["support"] == pytest.approx(1.0, rel=1e-6)
    assert result["grounded"] is True


# ---------------------------------------------------------------------------
# redact_pii
# ---------------------------------------------------------------------------

def test_redact_pii_email():
    text = "Contact me at alice@example.com for details."
    result = redact_pii(text)
    assert "alice@example.com" not in result
    assert "[redacted-email]" in result


def test_redact_pii_ssn():
    text = "SSN: 123-45-6789"
    result = redact_pii(text)
    assert "123-45-6789" not in result
    assert result == "SSN: [redacted-ssn]"


def test_redact_pii_phone():
    text = "Call 123-456-7890 now"
    result = redact_pii(text)
    assert "123-456-7890" not in result
    assert result == "Call [redacted-phone] now"


def test_redact_pii_card():
    text = "Card: 4111111111111111"
    result = redact_pii(text)
    assert "4111111111111111" not in result
    assert "[redacted-card]" in result


def test_redact_pii_no_pii_unchanged():
    text = "This is a plain sentence with no sensitive data."
    result = redact_pii(text)
    assert result == text


def test_redact_pii_multiple_types_in_one_text():
    text = "Email bob@example.com, SSN 987-65-4321."
    result = redact_pii(text)
    assert "bob@example.com" not in result
    assert "987-65-4321" not in result
    assert "[redacted-email]" in result
    assert "[redacted-ssn]" in result


def test_redact_pii_empty_string():
    assert redact_pii("") == ""
