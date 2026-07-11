"""Crucible's provider registry: oracle-gate's providers, extended not forked.

LongAnthropicProvider only raises max_tokens (generated test files exceed oracle-gate's
review-sized 4096 default). FakeProvider makes every loop path testable offline.

output_cap is a mechanical ceiling, not a suggestion: env._call checks the real
usage against it and raises TruncatedOutput when a reply hit the wall (protocol
v9 amendment -- a capped-but-undetected truncation produced empty/broken test
files that were rejected downstream with misleading notes, silently confounding
the experiment). Providers with no output_cap attribute (e.g. OpenAIProvider --
its request body carries no max_tokens) are never truncation-checked.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from oracle_gate.providers import AnthropicProvider, OpenAIProvider, Provider, Usage


class LongAnthropicProvider(AnthropicProvider):
    output_cap = 32000  # single source of truth: _body and env._call both read this
    # A reply approaching the 32k cap can stream server-side for many minutes;
    # oracle-gate's Provider.complete_with_usage hardcodes a 300s read timeout,
    # which aborted a real critic round mid-generation (graph-guard loop-same,
    # 2026-07-10: 3 read timeouts, cell verdict "aborted"). The base class offers
    # no timeout seam, so complete_with_usage is overridden verbatim except for
    # the timeout. Server-side limits still apply and fail loud as API errors.
    request_timeout = 1200

    def _body(self, model, system, user):
        body = super()._body(model, system, user)
        body["max_tokens"] = self.output_cap
        return body

    def complete_with_usage(self, system, user, model=None):
        model = model or self.default_model
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(self._body(model, system, user)).encode(),
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as r:
                data = json.load(r)
                return self._parse(data), self._parse_usage(data)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{self.name} API error {e.code}: {e.read().decode()[:800]}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"{self.name} network error: {e}") from None


class TruncatedOutput(RuntimeError):
    """A reply hit its provider's mechanical output_cap. Carries everything the
    loop needs to record the round honestly: the tokens were billed even though
    the reply is unusable, so the round must still be metered in receipts and
    the truncated text preserved as evidence -- never silently discarded."""

    def __init__(self, text: str, usage: Usage, model: str, prompt_sha256: str, cap: int):
        self.text = text
        self.usage = usage
        self.model = model
        self.prompt_sha256 = prompt_sha256
        self.cap = cap
        super().__init__(
            f"truncated: output hit max_tokens cap "
            f"(output_tokens={usage.output_tokens} >= max_tokens={cap})"
        )


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
