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
  env.validate(test_path) -> list[str]  (raises GuardrailViolation; returns names of any
    pristine-failing tests salvaged/dropped from the file -- v3 per-test salvage)
  env.remove_test_file(path) -> None  (a rejected round leaves no trace)
  env.assert_clean() -> None  (post-round integrity attestation; raises GuardrailViolation)
  env.cost_usd(model, usage) -> float
"""
from __future__ import annotations

from dataclasses import dataclass, field

from oracle_gate.providers import Usage

from crucible.engine import SandboxStatsFailure
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
    all_mutants: int = 0
    counts: dict = field(default_factory=dict)
    status: str = "ok"
    note: str = ""
    dropped_tests: list[str] = field(default_factory=list)


@dataclass
class LoopResult:
    rounds: list[RoundRecord]
    verdict: str
    total_cost_usd: float
    baseline_survivors: list[str] = field(default_factory=list)
    baseline_all_mutants: int = 0
    baseline_counts: dict = field(default_factory=dict)


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
        # an aborted round killed nothing: keep the survivor context rather than
        # letting the receipt read as "0 survivors left"
        rec.survivors_after = list(survivors_before)
        return rec

    rec.prompt_sha256, rec.model = reply.prompt_sha256, reply.model
    rec.usage_in, rec.usage_out = reply.usage.input_tokens, reply.usage.output_tokens
    rec.cost_usd = env.cost_usd(reply.model, reply.usage)

    path = None
    try:
        path = env.write_test_file(round_no, cfg.arm, reply.text)
        rec.test_file = path
        dropped = env.validate(path)
        rec.dropped_tests = list(dropped or [])
    except GuardrailViolation as exc:
        if path is not None:
            env.remove_test_file(path)
        rec.status, rec.note, rec.test_file = "rejected", str(exc), None
        rec.survivors_after = list(survivors_before)
        return rec

    try:
        after = env.measure()
    except SandboxStatsFailure as exc:
        # the generated test passed pristine validation but crashes mutmut's own
        # sandbox (e.g. it asserts a directory also_copy never carried in) --
        # NOT a legitimate zero-kill measurement. Reject the round rather than
        # ever recording the plausible-zero this would otherwise produce.
        env.remove_test_file(path)
        rec.status, rec.note, rec.test_file = "rejected", f"sandbox-invalid: {exc}", None
        rec.survivors_after = list(survivors_before)
        return rec

    try:
        # integrity attestation: executing the generated tests must not have
        # touched the tree; a tampered tree means the measurement is untrustworthy
        # and the run cannot continue.
        env.assert_clean()
    except GuardrailViolation as exc:
        rec.status, rec.note = "aborted", f"integrity: {exc}"
        rec.survivors_after = list(survivors_before)
        return rec

    rec.survivors_after = list(after.survivors)
    rec.kills = [m for m in survivors_before if m not in set(after.survivors)]
    rec.all_mutants = after.all_mutants
    rec.counts = dict(after.counts)
    return rec


def _run(env, cfg, rounds_budget, on_round=None) -> LoopResult:
    rounds: list[RoundRecord] = []

    # Pristine baseline: measure BEFORE any generated test exists, so round 0's
    # kills are real (tester kills = baseline survivors minus post-round survivors)
    # and the H1 arm comparison shares an honest denominator.
    pre = env.measure()

    def _result(verdict: str) -> LoopResult:
        return LoopResult(rounds, verdict, _cost(rounds),
                          baseline_survivors=list(pre.survivors),
                          baseline_all_mutants=pre.all_mutants,
                          baseline_counts=dict(pre.counts))

    first = _round(env, cfg, 0, "tester", survivors_before=pre.survivors)
    rounds.append(first)
    if on_round is not None:
        on_round(first)
    if first.status != "ok":
        # a run whose tester round never produced valid tests measured nothing;
        # "clean" must be impossible here
        return _result(first.status)
    survivors = first.survivors_after

    dry = 0
    for n in range(1, rounds_budget + 1):
        if not survivors:
            return _result("clean")
        rec = _round(env, cfg, n, "critic", survivors)
        rounds.append(rec)
        if on_round is not None:
            on_round(rec)
        if rec.status == "aborted":
            return _result("aborted")
        survivors = rec.survivors_after
        dry = dry + 1 if not rec.kills else 0
        if dry >= cfg.dry_rounds:
            return _result("dry")

    verdict = "clean" if not survivors else ("cap" if rounds_budget else "oneshot")
    return _result(verdict)


def _cost(rounds) -> float:
    return sum(r.cost_usd for r in rounds)


def harden(env, cfg: LoopConfig, on_round=None) -> LoopResult:
    return _run(env, cfg, rounds_budget=cfg.max_rounds, on_round=on_round)


def oneshot(env, cfg: LoopConfig, on_round=None) -> LoopResult:
    return _run(env, cfg, rounds_budget=0, on_round=on_round)
