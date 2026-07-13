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
  env.archive_rejected_text(round_no, arm, text) -> None  (preserve a truncated reply
    as evidence; never touches the subject clone)
  env.assert_clean() -> None  (post-round integrity attestation; raises GuardrailViolation)
  env.cost_usd(model, usage) -> float
"""
from __future__ import annotations

from dataclasses import dataclass, field

from oracle_gate.providers import Usage

from crucible.engine import SandboxStatsFailure
from crucible.guardrails import GuardrailViolation
from crucible.providers_ext import TruncatedOutput


class ReproductionMismatch(RuntimeError):
    """A PROTOCOL-B seeded continuation failed to reproduce the frozen seed's
    measurement (baseline drift, post-round-0 survivor drift, injection-time
    validation failure, or a resurrected mutant). The replicate is instrument-
    invalid and must never be scored; `rounds` carries whatever rounds were
    already receipted so the caller can cost them honestly."""

    def __init__(self, msg: str, rounds: list | None = None):
        super().__init__(msg)
        self.rounds = list(rounds or [])


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
    except TruncatedOutput as exc:
        # billed but unusable: record the round honestly (the tokens WERE spent)
        # and archive the reply as evidence, rather than let it read as a silent
        # model/network failure. Never retried upstream -- see env._call.
        rec.model, rec.prompt_sha256 = exc.model, exc.prompt_sha256
        rec.usage_in, rec.usage_out = exc.usage.input_tokens, exc.usage.output_tokens
        rec.cost_usd = env.cost_usd(exc.model, exc.usage)
        env.archive_rejected_text(round_no, cfg.arm, exc.text)
        rec.status, rec.note, rec.test_file = "rejected", str(exc), None
        rec.survivors_after = list(survivors_before)  # zero kills credited
        return rec
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
    return _critic_phase(env, cfg, rounds, first.survivors_after, rounds_budget,
                         on_round, _result, forbid_resurrection=False)


def _critic_phase(env, cfg, rounds, survivors, rounds_budget, on_round, result,
                  forbid_resurrection):
    """Rounds 1..N (shared by the fresh-round-0 and seeded paths — behavior of the
    fresh path is unchanged by the extraction). With forbid_resurrection (PROTOCOL-B
    §4), a mutant reappearing after it was measured killed is an instrument failure:
    the round is receipted first (evidence), then the run fails loud, never scored."""
    dry = 0
    for n in range(1, rounds_budget + 1):
        if not survivors:
            return result("clean")
        rec = _round(env, cfg, n, "critic", survivors)
        rounds.append(rec)
        if on_round is not None:
            on_round(rec)
        if forbid_resurrection:
            resurrected = set(rec.survivors_after) - set(survivors)
            if resurrected:
                raise ReproductionMismatch(
                    f"round {n} resurrected mutants {sorted(resurrected)}: a mutant "
                    "measured killed came back, so a non-deterministic test is in "
                    "play; the replicate is instrument-invalid (PROTOCOL-B §4)",
                    rounds=rounds)
        if rec.status == "aborted":
            return result("aborted")
        survivors = rec.survivors_after
        dry = dry + 1 if not rec.kills else 0
        if dry >= cfg.dry_rounds:
            return result("dry")

    verdict = "clean" if not survivors else ("cap" if rounds_budget else "oneshot")
    return result(verdict)


def seeded_run(env, cfg: LoopConfig, seed_text: str, expected_baseline, expected_post,
               on_round=None, seed_model: str = "", seed_prompt_sha256: str = "") -> LoopResult:
    """PROTOCOL-B seeded continuation: round 0 installs the frozen seed file instead
    of calling the Tester (zero marginal cost), verifies the frozen measurement
    reproduces exactly, then runs Critic rounds as in `harden`. Any reproduction
    failure raises ReproductionMismatch — the cell fails loud and is never scored."""
    rounds: list[RoundRecord] = []
    pre = env.measure()
    if set(pre.survivors) != set(expected_baseline):
        raise ReproductionMismatch(
            "pristine baseline differs from the frozen seed's: measured "
            f"{sorted(pre.survivors)} != frozen {sorted(expected_baseline)} "
            "(PROTOCOL-B §4 reproduction check)")

    def _result(verdict: str) -> LoopResult:
        return LoopResult(rounds, verdict, _cost(rounds),
                          baseline_survivors=list(pre.survivors),
                          baseline_all_mutants=pre.all_mutants,
                          baseline_counts=dict(pre.counts))

    rec = RoundRecord(round=0, role="tester", survivors_before=list(pre.survivors),
                      model=seed_model, prompt_sha256=seed_prompt_sha256,
                      note="frozen seed injected; zero marginal cost (PROTOCOL-B)")
    path = env.write_test_file(0, cfg.arm, seed_text)
    rec.test_file = path
    try:
        dropped = env.validate(path)
    except GuardrailViolation as exc:
        raise ReproductionMismatch(
            f"frozen seed failed pristine validation at injection: {exc} "
            "(PROTOCOL-B §4 seed re-validation)") from exc
    if dropped:
        raise ReproductionMismatch(
            f"injection-time salvage dropped {list(dropped)}: the frozen seed no "
            "longer passes pristine as frozen (PROTOCOL-B §4 seed re-validation)")
    try:
        after = env.measure()
    except SandboxStatsFailure as exc:
        raise ReproductionMismatch(
            f"frozen seed crashed the measurement sandbox at injection: {exc} "
            "(measured clean at freeze time, so the instrument changed)") from exc
    try:
        env.assert_clean()
    except GuardrailViolation as exc:
        # executing the frozen seed touched the tree: the shared starting state
        # is corrupt, the same instrument-failure class as a reproduction
        # mismatch -- never a raw crash that would leave the cell unreceipted
        raise ReproductionMismatch(
            f"tree integrity failed after seed injection: {exc} (PROTOCOL-B §4)") from exc
    if set(after.survivors) != set(expected_post):
        raise ReproductionMismatch(
            "post-round-0 survivors differ from the frozen seed's: measured "
            f"{sorted(after.survivors)} != frozen {sorted(expected_post)} "
            "(PROTOCOL-B §4 reproduction check)")
    rec.survivors_after = list(after.survivors)
    rec.kills = [m for m in pre.survivors if m not in set(after.survivors)]
    rec.all_mutants = after.all_mutants
    rec.counts = dict(after.counts)
    rounds.append(rec)
    if on_round is not None:
        on_round(rec)
    return _critic_phase(env, cfg, rounds, rec.survivors_after, cfg.max_rounds,
                         on_round, _result, forbid_resurrection=True)


def _cost(rounds) -> float:
    return sum(r.cost_usd for r in rounds)


def harden(env, cfg: LoopConfig, on_round=None) -> LoopResult:
    return _run(env, cfg, rounds_budget=cfg.max_rounds, on_round=on_round)


def oneshot(env, cfg: LoopConfig, on_round=None) -> LoopResult:
    return _run(env, cfg, rounds_budget=0, on_round=on_round)
