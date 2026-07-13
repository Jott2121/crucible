"""Experiment B (PROTOCOL-B): frozen shared round-0, causal isolation of the critic loop.

Phase A (`--phase seed`) draws one Tester round 0 per replicate and freezes it under
`experiments/seeds/<subject>/rep<k>/`; Phase B (`--phase run`) runs a continuation
(no-critic / seeded-harden) from that frozen state. Both phases enforce the
pre-registration mechanically: the protocol file AND the seed directory must be
committed byte-identical to HEAD before a continuation runs, draw caps are counted
from receipts on disk, and any reproduction failure invalidates the cell loudly
(`crucible.loop.ReproductionMismatch`) instead of ever scoring it.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from crucible.experiment import ProtocolError, assert_protocol_committed
from crucible.providers_ext import get_provider

VALID_B_MODES = ("seed-only", "seeded-harden")
_REQUIRED_KEYS = ("protocol_b_version", "tester", "rounds", "replicates",
                  "seeds_dir", "runs_dir", "arms", "subjects")
_REQUIRED_REPLICATE_KEYS = ("k", "max_seed_draws_per_replicate",
                            "max_total_seed_draws_per_subject")


class ProtocolBError(ProtocolError):
    """The Experiment-B protocol/seed state is invalid, uncommitted, or violated."""


def load_protocol_b(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in _REQUIRED_KEYS:
        if key not in data:
            raise ProtocolBError(f"protocol-b missing required key {key!r}")
    for key in _REQUIRED_REPLICATE_KEYS:
        value = data["replicates"].get(key)
        if not isinstance(value, int) or value < 1:
            raise ProtocolBError(f"replicates.{key} must be a positive int, got {value!r}")
    for key in ("max_rounds", "dry_rounds"):
        value = data["rounds"].get(key)
        if not isinstance(value, int) or value < 1:
            raise ProtocolBError(f"rounds.{key} must be a positive int, got {value!r}")
    seed_only = [n for n, arm in data["arms"].items() if arm.get("mode") == "seed-only"]
    for name, arm in data["arms"].items():
        if arm.get("mode") not in VALID_B_MODES:
            raise ProtocolBError(f"arm {name!r} has invalid mode {arm.get('mode')!r}")
        if arm["mode"] == "seeded-harden" and "critic" not in arm:
            raise ProtocolBError(f"seeded-harden arm {name!r} needs a critic")
    if len(seed_only) != 1:
        raise ProtocolBError(f"protocol-b needs exactly one seed-only arm, got {seed_only}")
    for subj_name, scope in data["subjects"].items():
        if "module" not in scope:
            raise ProtocolBError(f"subject {subj_name!r} scope missing required key 'module'")
    return data


def assert_dir_committed(repo_root, dir_path, run=subprocess.run) -> None:
    """The frozen-seed analogue of assert_protocol_committed: every file under
    dir_path must exist in HEAD with identical content, and no file recorded in
    HEAD under that path may be missing from disk. This is what makes the shared
    starting state verifiable from the public record (PROTOCOL-B §2)."""
    repo_root = Path(repo_root)
    dir_path = Path(dir_path)
    rel = str(dir_path.resolve().relative_to(repo_root.resolve()))
    on_disk = sorted(str(p.relative_to(dir_path)) for p in dir_path.rglob("*") if p.is_file())
    if not on_disk:
        raise ProtocolBError(f"{rel} is empty or missing; there is no frozen seed to run from")
    proc = run(["git", "ls-tree", "-r", "--name-only", "HEAD", "--", rel],
               cwd=str(repo_root), capture_output=True, text=True)
    if proc.returncode != 0:
        raise ProtocolBError(f"git ls-tree failed for {rel}: {(proc.stderr or '').strip()}")
    in_head = sorted(line[len(rel) + 1:] for line in proc.stdout.splitlines() if line)
    if on_disk != in_head:
        raise ProtocolBError(
            f"{rel} differs from HEAD (files on disk {on_disk} vs committed {in_head}); "
            "commit the frozen seed before running a continuation")
    for name in on_disk:
        shown = run(["git", "show", f"HEAD:{rel}/{name}"], cwd=str(repo_root),
                    capture_output=True, text=True)
        if shown.returncode != 0 or shown.stdout != (dir_path / name).read_text(encoding="utf-8"):
            raise ProtocolBError(
                f"{rel}/{name} differs from HEAD; commit the frozen seed before "
                "running a continuation")


def _assert_api_billing(role: str, provider) -> None:
    billing = getattr(provider, "billing", "api")
    if billing != "api":
        raise ValueError(
            f"experiment-b refuses {role} provider {getattr(provider, 'name', provider)!r}: "
            f"billing={billing!r} -- pre-registered runs require metered API spend")


def _subject_scope(protocol: dict, subject_dir, module_path: str) -> dict:
    subject_name = Path(subject_dir).name
    subjects = protocol.get("subjects", {})
    if subject_name not in subjects:
        raise ProtocolBError(
            f"subject {subject_name!r} is not in protocol-b subjects; the scope must "
            "be frozen in the protocol before this cell can run")
    scope = subjects[subject_name]
    if scope["module"] != module_path:
        raise ProtocolBError(
            f"subject {subject_name!r} protocol module {scope['module']!r} does not "
            f"match --module {module_path!r}")
    return scope


def _count_draws(rep_dir: Path) -> int:
    return len(list((rep_dir / "draws").glob("draw-*"))) if (rep_dir / "draws").exists() else 0


def _count_subject_draws(subject_seeds: Path) -> int:
    return sum(_count_draws(rep) for rep in subject_seeds.glob("rep*") if rep.is_dir())


_SEED_KEYS = ("module", "head_sha", "baseline_survivors", "baseline_all_mutants",
              "baseline_counts", "post_survivors", "post_counts", "test_sha256",
              "provenance")


def _load_seed(rep_dir: Path) -> tuple[dict, str]:
    seed_path = rep_dir / "seed.json"
    test_path = rep_dir / "seed_test.py"
    if not seed_path.exists() or not test_path.exists():
        raise ProtocolBError(f"no frozen seed at {rep_dir} (seed.json + seed_test.py required)")
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    for key in _SEED_KEYS:
        if key not in seed:
            raise ProtocolBError(f"frozen seed {seed_path} missing required key {key!r}")
    text = test_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest != seed["test_sha256"]:
        raise ProtocolBError(
            f"seed_test.py sha256 {digest} does not match seed.json's "
            f"{seed['test_sha256']}; the frozen seed is self-inconsistent")
    return seed, text


def _make_env(protocol, arm_critic_cfg, subject_dir, module_path, scope):
    from crucible.env import SubjectEnv

    tester = get_provider(protocol["tester"]["provider"])
    critic = (tester if arm_critic_cfg == protocol["tester"]
              else get_provider(arm_critic_cfg["provider"]))
    _assert_api_billing("tester", tester)
    _assert_api_billing("critic", critic)
    env = SubjectEnv(
        subject_dir=Path(subject_dir),
        tester_provider=tester, tester_model=protocol["tester"]["model"],
        critic_provider=critic, critic_model=arm_critic_cfg["model"],
        module_path=module_path, scope=scope,
    )
    return env, critic


def generate_seed(protocol: dict, subject_dir, module_path: str, seeds_root) -> int:
    """Phase A: one Tester draw. Receipted whether accepted or rejected; caps are
    counted from the draw receipts already on disk, so they cannot be forgotten."""
    from datetime import datetime, timezone

    from crucible.loop import LoopConfig, oneshot
    from crucible.receipts import ReceiptWriter

    scope = _subject_scope(protocol, subject_dir, module_path)
    subject_name = Path(subject_dir).name
    caps = protocol["replicates"]

    subject_seeds = Path(seeds_root) / subject_name
    # A cap-exhausted replicate is scored MISSING and skipped (PROTOCOL-B §2) --
    # it must never block the other replicates' draws.
    rep = _next_rep_needing_seed(subject_seeds, caps["k"],
                                 caps["max_seed_draws_per_replicate"])
    if rep is None:
        seedless = [r for r in range(1, caps["k"] + 1)
                    if not (subject_seeds / f"rep{r}" / "seed.json").exists()]
        if seedless:
            print(f"replicates {seedless} of {subject_name} are seedless with their "
                  f"{caps['max_seed_draws_per_replicate']}-draw cap exhausted: "
                  "MISSING per PROTOCOL-B §2 (DEVIATIONS entry required); no further draws")
            return 3
        print(f"all {caps['k']} replicates for {subject_name} already have frozen seeds")
        return 0
    rep_dir = subject_seeds / f"rep{rep}"
    if _count_subject_draws(subject_seeds) >= caps["max_total_seed_draws_per_subject"]:
        raise ProtocolBError(
            f"subject {subject_name} has exhausted its "
            f"{caps['max_total_seed_draws_per_subject']}-draw cap (PROTOCOL-B §2); "
            "remaining seedless replicates are missing -- no further draws")

    env, _ = _make_env(protocol, protocol["tester"], subject_dir, module_path, scope)
    env.reset_clone()
    head_sha = env.preflight(module_path)

    draw_no = _count_draws(rep_dir) + 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    draw_dir = rep_dir / "draws" / f"draw-{draw_no}"
    writer = ReceiptWriter(draw_dir, {
        "phase": "seed", "subject": str(subject_dir), "module": module_path,
        "rep": rep, "draw": draw_no, "head_sha": head_sha,
        "protocol_b_version": protocol["protocol_b_version"],
        "tester_provider": protocol["tester"]["provider"],
        "tester_model": protocol["tester"]["model"],
        "tester_billing": getattr(env.tester_provider, "billing", "api"),
        "started_at": stamp,
    })
    env.set_artifact_dir(draw_dir)
    cfg = LoopConfig(max_rounds=protocol["rounds"]["max_rounds"],
                     dry_rounds=protocol["rounds"]["dry_rounds"], arm="seed")
    result = oneshot(env, cfg, on_round=writer.append)
    writer.finish(result.verdict, result.total_cost_usd, extra={
        "baseline_survivors": result.baseline_survivors,
        "baseline_all_mutants": result.baseline_all_mutants,
        "baseline_counts": result.baseline_counts,
    })
    if result.verdict not in ("oneshot", "clean"):
        print(f"seed draw {subject_name}/rep{rep}/draw-{draw_no}: REJECTED "
              f"(verdict={result.verdict}); receipted, never used as a seed")
        return 3

    rec = result.rounds[0]
    text = (Path(subject_dir) / rec.test_file).read_text(encoding="utf-8")
    (rep_dir / "seed_test.py").write_text(text, encoding="utf-8")
    (rep_dir / "seed.json").write_text(json.dumps({
        "subject": subject_name, "rep": rep, "module": module_path,
        "head_sha": head_sha, "draw": draw_no,
        "baseline_survivors": result.baseline_survivors,
        "baseline_all_mutants": result.baseline_all_mutants,
        "baseline_counts": result.baseline_counts,
        "post_survivors": rec.survivors_after,
        "post_counts": rec.counts,
        "test_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "provenance": {"model": rec.model, "prompt_sha256": rec.prompt_sha256,
                       "usage_in": rec.usage_in, "usage_out": rec.usage_out,
                       "cost_usd": rec.cost_usd, "dropped_tests": rec.dropped_tests,
                       "generated_at": stamp},
    }, indent=2), encoding="utf-8")
    print(f"seed frozen: {subject_name}/rep{rep} draw {draw_no} "
          f"(baseline {len(result.baseline_survivors)} survivors, "
          f"round-0 killed {len(rec.kills)}, {len(rec.survivors_after)} remain) "
          f"-- commit {rep_dir} before any continuation")
    return 0


def _next_rep_needing_seed(subject_seeds: Path, k: int, max_per_rep: int) -> int | None:
    """First replicate that still needs a seed AND may still draw one. A seedless
    replicate whose per-replicate cap is spent is MISSING (PROTOCOL-B §2), never a
    blocker for the replicates after it."""
    for rep in range(1, k + 1):
        rep_dir = subject_seeds / f"rep{rep}"
        if (rep_dir / "seed.json").exists():
            continue
        if _count_draws(rep_dir) >= max_per_rep:
            continue
        return rep
    return None


def retire_seed(seeds_root, subject_name: str, rep: int, reason: str) -> int:
    """PROTOCOL-B §4 invalidation: the seed is retired in place (kept on disk,
    marked invalid) so its draws still count against both caps. Mandatory next
    step per the protocol: draw a replacement (caps permitting) + DEVIATIONS entry."""
    from datetime import datetime, timezone

    rep_dir = Path(seeds_root) / subject_name / f"rep{rep}"
    seed, _ = _load_seed(rep_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (rep_dir / "seed.json").rename(rep_dir / f"seed-invalid-{stamp}.json")
    (rep_dir / "seed_test.py").rename(rep_dir / f"seed_test-invalid-{stamp}.py")
    (rep_dir / f"retired-{stamp}.json").write_text(json.dumps({
        "reason": reason, "retired_at": stamp, "draw": seed["draw"],
    }, indent=2), encoding="utf-8")
    print(f"seed {subject_name}/rep{rep} retired ({reason}); draws still count "
          "against both caps. Draw a replacement if caps permit + add the "
          "DEVIATIONS.md entry (PROTOCOL-B §4).")
    return 0


def _assert_cell_runnable(runs_root, subject_name: str, arm_name: str, rep: int,
                          seed_sha: str) -> None:
    """Mechanical §7/§8 enforcement: a validly scored cell is never rerun, an
    invalid cell's replicate goes through seed retirement (never a continuation
    rerun), and an aborted/crashed cell gets exactly one rerun, then it is missing.
    Decided entirely from receipts on disk -- no operator discretion.

    Scoped to the CURRENT frozen seed (meta.json's seed.test_sha256): receipts
    belonging to a retired seed's cells are §4 DEVIATIONS material, never a block
    on the mandatory replacement seed's continuations -- without this scoping the
    §4 replacement flow would be mechanically unexecutable (review finding B3)."""
    cell_dirs = sorted((Path(runs_root) / subject_name).glob(f"{arm_name}-rep{rep}-*"))
    aborted_attempts = 0
    for d in cell_dirs:
        meta_path = d / "meta.json"
        if meta_path.exists():
            meta_sha = (json.loads(meta_path.read_text(encoding="utf-8"))
                        .get("seed", {}).get("test_sha256"))
            if meta_sha is not None and meta_sha != seed_sha:
                continue  # a retired seed's cell -- out of scope for this seed
        # a meta-less dir cannot come from a real run (ReceiptWriter writes meta
        # first); treat it as an abort-class attempt for THIS seed, conservatively
        result_path = d / "result.json"
        if not result_path.exists():
            # crashed mid-run: an abort-class attempt (receipted rounds, no verdict)
            aborted_attempts += 1
            continue
        verdict = json.loads(result_path.read_text(encoding="utf-8"))["verdict"]
        if verdict in ("clean", "dry", "cap", "oneshot"):
            raise ProtocolBError(
                f"cell {subject_name}/{arm_name}/rep{rep} is already validly scored "
                f"({verdict!r} in {d.name}); a scored cell is never rerun "
                "(PROTOCOL-B §8)")
        if verdict == "invalid":
            raise ProtocolBError(
                f"cell {subject_name}/{arm_name}/rep{rep} was scored invalid "
                f"({d.name}); the replicate is invalidated -- retire the seed and "
                "draw a replacement (PROTOCOL-B §4), never rerun the continuation")
        aborted_attempts += 1
    if aborted_attempts >= 2:
        raise ProtocolBError(
            f"cell {subject_name}/{arm_name}/rep{rep} already aborted "
            f"{aborted_attempts} times; §7 permits exactly one rerun -- the cell "
            "is MISSING (DEVIATIONS entry required), no further attempts")
    if aborted_attempts == 1:
        print(f"note: this is {subject_name}/{arm_name}/rep{rep}'s single mandatory "
              "§7 rerun after an abort (DEVIATIONS entry required)")


def run_continuation(protocol: dict, arm_name: str, subject_dir, module_path: str,
                     seeds_root, runs_root, repo_root, rep: int,
                     run=subprocess.run) -> int:
    """Phase B: one continuation cell from a committed frozen seed."""
    from datetime import datetime, timezone

    from crucible.loop import LoopConfig, ReproductionMismatch, seeded_run
    from crucible.receipts import ReceiptWriter

    arm = protocol["arms"].get(arm_name)
    if arm is None:
        raise ProtocolBError(f"arm {arm_name!r} is not in protocol-b arms")
    k = protocol["replicates"]["k"]
    if not 1 <= rep <= k:
        raise ProtocolBError(f"--rep {rep} is outside the pre-registered 1..{k} range")
    scope = _subject_scope(protocol, subject_dir, module_path)
    subject_name = Path(subject_dir).name
    rep_dir = Path(seeds_root) / subject_name / f"rep{rep}"
    assert_dir_committed(repo_root, rep_dir, run=run)
    seed, seed_text = _load_seed(rep_dir)
    if seed["module"] != module_path:
        raise ProtocolBError(
            f"seed module {seed['module']!r} does not match --module {module_path!r}")
    # the rerun gate is scoped to THIS frozen seed; still strictly pre-paid-call
    _assert_cell_runnable(runs_root, subject_name, arm_name, rep, seed["test_sha256"])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(runs_root) / subject_name / f"{arm_name}-rep{rep}-{stamp}"
    seed_ref = {"seed_dir": str(rep_dir), "test_sha256": seed["test_sha256"],
                "seed_head_sha": seed["head_sha"], "rep": rep}

    if arm["mode"] == "seed-only":
        # Derived cell: the frozen round 0 IS this arm's outcome (PROTOCOL-B §2);
        # no model call, no clone touch, zero marginal cost.
        writer = ReceiptWriter(run_dir, {
            "phase": "run", "arm": arm_name, "subject": str(subject_dir),
            "module": module_path, "head_sha": seed["head_sha"],
            "protocol_b_version": protocol["protocol_b_version"],
            "seed": seed_ref, "started_at": stamp, "derived": True,
        })
        from crucible.loop import RoundRecord
        prov = seed["provenance"]
        rec = RoundRecord(
            round=0, role="tester", model=prov["model"],
            prompt_sha256=prov["prompt_sha256"],
            test_file="<frozen-seed>", survivors_before=list(seed["baseline_survivors"]),
            survivors_after=list(seed["post_survivors"]),
            kills=[m for m in seed["baseline_survivors"]
                   if m not in set(seed["post_survivors"])],
            all_mutants=seed["baseline_all_mutants"],
            counts=dict(seed["post_counts"]),
            note="derived from frozen seed; marginal cost 0 (seed spend receipted "
                 "in the seed's own draw receipt, PROTOCOL-B §5)")
        writer.append(rec)
        verdict = "clean" if not seed["post_survivors"] else "oneshot"
        writer.finish(verdict, 0.0, extra={
            "baseline_survivors": seed["baseline_survivors"],
            "baseline_all_mutants": seed["baseline_all_mutants"],
            "baseline_counts": seed["baseline_counts"],
        })
        print(f"{arm_name} on {subject_name}/rep{rep}: verdict={verdict} cost=$0.0000 "
              f"(derived) receipt={run_dir}")
        return 0

    env, critic = _make_env(protocol, arm["critic"], subject_dir, module_path, scope)
    env.reset_clone()
    head_sha = env.preflight(module_path)
    if head_sha != seed["head_sha"]:
        raise ProtocolBError(
            f"subject HEAD {head_sha} differs from the seed's frozen {seed['head_sha']}; "
            "the subject drifted since freeze -- instrument failure, cell not run")

    writer = ReceiptWriter(run_dir, {
        "phase": "run", "arm": arm_name, "subject": str(subject_dir),
        "module": module_path, "head_sha": head_sha,
        "protocol_b_version": protocol["protocol_b_version"],
        "tester_provider": protocol["tester"]["provider"],
        "tester_model": protocol["tester"]["model"],
        "critic_provider": arm["critic"]["provider"],
        "critic_model": arm["critic"]["model"],
        "critic_billing": getattr(critic, "billing", "api"),
        "seed": seed_ref, "started_at": stamp,
        "max_rounds": protocol["rounds"]["max_rounds"],
        "dry_rounds": protocol["rounds"]["dry_rounds"],
    })
    env.set_artifact_dir(run_dir)
    cfg = LoopConfig(max_rounds=protocol["rounds"]["max_rounds"],
                     dry_rounds=protocol["rounds"]["dry_rounds"], arm=arm_name)
    prov = seed["provenance"]
    try:
        result = seeded_run(env, cfg, seed_text,
                            seed["baseline_survivors"], seed["post_survivors"],
                            on_round=writer.append, seed_model=prov["model"],
                            seed_prompt_sha256=prov["prompt_sha256"])
    except ReproductionMismatch as exc:
        cost = sum(r.cost_usd for r in exc.rounds)
        writer.finish("invalid", cost, extra={"invalid_reason": str(exc)})
        print(f"{arm_name} on {subject_name}/rep{rep}: INVALID -- {exc}\n"
              f"replicate must be invalidated per PROTOCOL-B §4; receipt={run_dir}")
        return 4
    writer.finish(result.verdict, result.total_cost_usd, extra={
        "baseline_survivors": result.baseline_survivors,
        "baseline_all_mutants": result.baseline_all_mutants,
        "baseline_counts": result.baseline_counts,
    })
    accepted_dir = run_dir / "accepted"
    accepted_count = 0
    for p in sorted((Path(subject_dir) / "tests").glob("crucible_*_test.py")):
        accepted_dir.mkdir(exist_ok=True)
        shutil.copy2(p, accepted_dir / p.name)
        accepted_count += 1
    print(f"{arm_name} on {subject_name}/rep{rep}: verdict={result.verdict} "
          f"cost=${result.total_cost_usd:.4f} receipt={run_dir} "
          f"(archived {accepted_count} tests)")
    return 3 if result.verdict in ("aborted", "rejected") else 0


def dispatch(args, repo_root) -> int:
    """CLI entry: shared pre-registration gate, then per-phase routing."""
    assert_protocol_committed(repo_root, Path(args.protocol))
    protocol = load_protocol_b(args.protocol)
    seeds_root = Path(repo_root) / protocol["seeds_dir"]
    runs_root = Path(repo_root) / protocol["runs_dir"]
    if args.phase == "seed":
        if not args.module:
            raise ProtocolBError("--module is required for --phase seed")
        if args.rep is not None:
            raise ProtocolBError(
                "--rep is not accepted for --phase seed: the target replicate is "
                "auto-selected (first seedless replicate whose caps permit a draw), "
                "so no draw can be aimed by hand")
        return generate_seed(protocol, args.subject, args.module, seeds_root)
    if args.phase == "retire-seed":
        if not args.reason:
            raise ProtocolBError("--reason is required to retire a seed (it goes in the record)")
        if args.rep is None:
            raise ProtocolBError("--rep is required for --phase retire-seed")
        return retire_seed(seeds_root, Path(args.subject).name, args.rep, args.reason)
    if not args.arm:
        raise ProtocolBError("--arm is required for --phase run")
    if args.rep is None:
        raise ProtocolBError("--rep is required for --phase run")
    if not args.module:
        raise ProtocolBError("--module is required for --phase run")
    return run_continuation(protocol, args.arm, args.subject, args.module,
                            seeds_root, runs_root, repo_root, args.rep)
