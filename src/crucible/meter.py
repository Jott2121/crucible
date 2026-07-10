"""Exact dollar cost from provider-reported usage.

agent-cost-attribution prices with a blended-rate ESTIMATE because its telemetry has no
input/output split. Crucible has the split (oracle_gate Usage), so it prices exactly from
the same PRICES table. Models the meter doesn't know (GPT) live in RATES_EXTRA. An unknown
model raises rather than pricing wrong: a cost-per-kill paper cannot contain a guessed rate.
"""
from __future__ import annotations

from agent_cost_attribution.pricing import PRICES, _tier
from oracle_gate.providers import Usage

# $ per 1M tokens (input, output). Verify against the provider's live pricing page
# when a rate is first used in a paid run; update here with the verification date.
RATES_EXTRA = {
    # verified 2026-07-10 against openai.com announcement (+2 independents)
    "gpt-5.6-terra": (2.50, 15.0),
}


class UnpricedModel(ValueError):
    """No verified rate for this model; refusing to guess."""


def _rates(model: str) -> tuple[float, float]:
    tier = _tier(model)
    if tier is not None:
        return PRICES[tier]
    rates = RATES_EXTRA.get((model or "").lower())
    if rates is not None:
        return rates
    raise UnpricedModel(f"no verified $/MTok rate for {model!r}; add it to RATES_EXTRA")


def cost_usd(model: str, usage: Usage) -> float:
    inp, outp = _rates(model)
    return (usage.input_tokens * inp + usage.output_tokens * outp) / 1_000_000.0
