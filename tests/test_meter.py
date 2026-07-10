import pytest
from oracle_gate.providers import Usage

from crucible.meter import UnpricedModel, cost_usd


def test_claude_tier_priced_from_meter_table():
    # sonnet: $3/MTok in, $15/MTok out (agent-cost-attribution PRICES)
    assert cost_usd("claude-sonnet-5", Usage(1_000_000, 1_000_000)) == pytest.approx(18.0)


def test_fable_tier():
    assert cost_usd("claude-fable-5", Usage(2_000_000, 0)) == pytest.approx(20.0)


def test_gpt_priced_from_extra_table():
    # RATES_EXTRA carries what the meter doesn't: gpt-5.6 at ($1.75, $14) per MTok
    assert cost_usd("gpt-5.6", Usage(1_000_000, 1_000_000)) == pytest.approx(15.75)


def test_gpt_variant_is_not_silently_priced_at_base_rate():
    # exact match only: a distinct-priced future variant must fail closed
    with pytest.raises(UnpricedModel):
        cost_usd("gpt-5.6-preview", Usage(10, 10))


def test_unknown_model_fails_closed():
    with pytest.raises(UnpricedModel):
        cost_usd("mystery-model-9", Usage(10, 10))
