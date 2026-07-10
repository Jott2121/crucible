"""Crucible's provider registry: oracle-gate's providers, extended not forked.

LongAnthropicProvider only raises max_tokens (generated test files exceed oracle-gate's
review-sized 4096 default). FakeProvider makes every loop path testable offline.
"""
from __future__ import annotations

from oracle_gate.providers import AnthropicProvider, OpenAIProvider, Provider, Usage


class LongAnthropicProvider(AnthropicProvider):
    def _body(self, model, system, user):
        body = super()._body(model, system, user)
        body["max_tokens"] = 16000
        return body


class FakeProvider(Provider):
    name = "fake"
    lineage = "fake"
    default_model = "fake-model"

    def __init__(self, replies):
        self.replies = list(replies)

    def complete_with_usage(self, system, user, model=None):
        if not self.replies:
            raise RuntimeError("FakeProvider exhausted: more model calls than scripted replies")
        return self.replies.pop(0), Usage(1000, 500)


def get_provider(name: str) -> Provider:
    registry = {
        "anthropic": LongAnthropicProvider,
        "openai": OpenAIProvider,
        "fake": lambda: FakeProvider([]),
    }
    if name not in registry:
        raise KeyError(f"unknown provider {name!r}; known: {sorted(registry)}")
    return registry[name]()
