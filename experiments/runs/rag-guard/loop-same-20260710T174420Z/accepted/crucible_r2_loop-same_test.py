import pytest
from rag_guard.guard import should_refuse, groundedness, redact_pii, _content_tokens


def test_content_tokens_empty_string_returns_empty_set():
    assert _content_tokens("") == set()
    assert _content_tokens(None) == set()


def test_content_tokens_filters_stopwords_not_keeps_them():
    # "the" is a stopword and must be removed, "cat" is content and kept.
    assert _content_tokens("the cat") == {"cat"}


def test_groundedness_empty_answer_dict_shape_and_values():
    result = groundedness("", ["cat dog"])
    assert result == {"grounded": False, "support": 0.0}


def test_groundedness_merges_tokens_across_multiple_contexts():
    # Both context strings contribute tokens; without proper union merging,
    # only the last context's tokens would survive.
    result = groundedness("cat dog", ["cat lives here", "dog runs there"])
    assert result["grounded"] is True
    assert result["support"] == pytest.approx(1.0, rel=1e-6)


def test_groundedness_boundary_equal_to_threshold_is_grounded():
    # support == threshold (0.5) must count as grounded (>=, not >).
    result = groundedness("cat dog", ["cat forest"])
    assert result["support"] == pytest.approx(0.5, rel=1e-6)
    assert result["grounded"] is True


def test_groundedness_support_rounded_to_four_decimals():
    # 2/7 = 0.285714285... -> rounds to 0.2857 at 4 decimals (not 0.28571
    # at 5 decimals, and not an integer 0 or 4).
    answer = "apple banana cherry date fig grape kiwi"
    contexts = ["apple banana lemon mango"]
    result = groundedness(answer, contexts)
    assert result["support"] == pytest.approx(0.2857, rel=1e-6)


def test_should_refuse_default_min_score_is_low():
    hits = [{"score": 0.1}]
    assert should_refuse(hits) is False


def test_should_refuse_missing_score_defaults_to_zero():
    hits = [{}]
    assert should_refuse(hits) is True


def test_should_refuse_equal_to_min_score_not_refused():
    # score exactly equal to min_score must NOT trigger refusal (< not <=).
    hits = [{"score": 0.05}]
    assert should_refuse(hits) is False


def test_redact_pii_masks_all_pii_types_with_exact_literals():
    text = (
        "Email: foo@bar.com, SSN: 123-45-6789, "
        "Phone: 123-456-7890, Card: 4111111111111111"
    )
    result = redact_pii(text)
    assert "[redacted-email]" in result
    assert "[redacted-ssn]" in result
    assert "[redacted-phone]" in result
    assert "[redacted-card]" in result
    assert "foo@bar.com" not in result
    assert "123-45-6789" not in result
    assert "123-456-7890" not in result
    assert "4111111111111111" not in result
