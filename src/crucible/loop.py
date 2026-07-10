"""The adversarial loop. Pure control flow: every effect goes through the injected env,
so this file is unit-tested with fakes and mutation-tested for real (dogfood, Task 12).

Round 0: the Tester writes tests from the module alone. Rounds 1..N: the Critic sees the
named survivors and aims at exactly those. Verdicts are mechanical throughout — a mutant
is killed by pytest or it survives; no model opinion is ever consulted.

The `env` duck-type (implemented for real in Task 11's CLI, faked in tests):
  env.measure() -> MutationOutcome
  env.survivor_diff(mutant_id) -> str
  env.call_tester() -> RoundReply
  env.call_critic(survivor_diffs: dict[str, str]) -> RoundReply
  env.write_test_file(round_no, arm, content) -> str  (repo-relative path; add-only check)
  env.validate(test_path) -> None  (raises GuardrailViolation)
  env.remove_test_file(path) -> None  (a rejected round leaves no trace)
  env.cost_usd(model, usage) -> float
"""
from __future__ import annotations

from dataclasses import dataclass, field

from oracle_gate.providers import Usage

from crucible.guardrails import GuardrailViolation


@dataclass(frozen=True)
class RoundReply:
    text: str
    prompt_sha256: str
    model: str
    usage: Usage


@dataclass(frozen=True)
class LoopConfig:
    max_rounds: int = 5
    dry_rounds: int = 2
    arm: str = "loop"


@dataclass
class RoundRecord:
    round: int
    role: str
    prompt_sha256: str = ""
    model: str = ""
    usage_in: int = 0
    usage_out: int = 0
    cost_usd: float = 0.0
    test_file: str | None = None
    survivors_before: list[str] = field(default_factory=list)
    survivors_after: list[str] = field(default_factory=list)
    kills: list[str] = field(default_factory=list)
    status: str = "ok"
    note: str = ""


@dataclass
class LoopResult:
    rounds: list[RoundRecord]
    verdict: str
    total_cost_usd: float


def _round(env, cfg, round_no, role, survivors_before) -> RoundRecord:
    rec = RoundRecord(round=round_no, role=role, survivors_before=list(survivors_before))
    try:
        if role == "tester":
            reply = env.call_tester()
        else:
            diffs = {mid: env.survivor_diff(mid) for mid in survivors_before}
            reply = env.call_critic(diffs)
    except Exception as exc:  # model/network failure after env-level retries
        rec.status, rec.note = "aborted", f"model call failed: {type(exc).__name__}: {exc}"
        return rec

    rec.prompt_sha256, rec.model = reply.prompt_sha256, reply.model
    rec.usage_in, rec.usage_out = reply.usage.input_tokens, reply.usage.output_tokens
    rec.cost_usd = env.cost_usd(reply.model, reply.usage)

    path = None
    try:
        path = env.write_test_file(round_no, cfg.arm, reply.text)
        rec.test_file = path
        env.validate(path)
    except GuardrailViolation as exc:
        if path is not None:
            env.remove_test_file(path)
        rec.status, rec.note, rec.test_file = "rejected", str(exc), None
        rec.survivors_after = list(survivors_before)
        return rec

    after = env.measure()
    rec.survivors_after = list(after.survivors)
    rec.kills = [m for m in survivors_before if m not in set(after.survivors)]
    return rec


def _run(env, cfg, rounds_budget) -> LoopResult:
    rounds: list[RoundRecord] = []

    first = _round(env, cfg, 0, "tester", survivors_before=[])
    rounds.append(first)
    if first.status == "aborted":
        return LoopResult(rounds, "aborted", _cost(rounds))
    survivors = first.survivors_after

    dry = 0
    for n in range(1, rounds_budget + 1):
        if not survivors:
            return LoopResult(rounds, "clean", _cost(rounds))
        rec = _round(env, cfg, n, "critic", survivors)
        rounds.append(rec)
        if rec.status == "aborted":
            return LoopResult(rounds, "aborted", _cost(rounds))
        survivors = rec.survivors_after
        dry = dry + 1 if not rec.kills else 0
        if dry >= cfg.dry_rounds:
            return LoopResult(rounds, "dry", _cost(rounds))

    verdict = "clean" if not survivors else ("cap" if rounds_budget else "oneshot")
    return LoopResult(rounds, verdict, _cost(rounds))


def _cost(rounds) -> float:
    return sum(r.cost_usd for r in rounds)


def harden(env, cfg: LoopConfig) -> LoopResult:
    return _run(env, cfg, rounds_budget=cfg.max_rounds)


def oneshot(env, cfg: LoopConfig) -> LoopResult:
    return _run(env, cfg, rounds_budget=0)
