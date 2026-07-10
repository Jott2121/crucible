"""Pre-registration enforcement + arm runner.

`crucible experiment` runs one (arm, subject) cell of the pre-registered design. It
refuses to run unless the protocol file is committed and byte-identical to HEAD —
the mechanical form of "the protocol was frozen before the data existed."
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

VALID_MODES = ("oneshot", "harden")


class ProtocolError(RuntimeError):
    """The protocol file is invalid, uncommitted, or modified."""


def load_protocol(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("protocol_version", "tester", "rounds", "arms"):
        if key not in data:
            raise ProtocolError(f"protocol missing required key {key!r}")
    for name, arm in data["arms"].items():
        if arm.get("mode") not in VALID_MODES:
            raise ProtocolError(f"arm {name!r} has invalid mode {arm.get('mode')!r}")
        if arm["mode"] == "harden" and "critic" not in arm:
            raise ProtocolError(f"harden arm {name!r} needs a critic")
    subjects = data.get("subjects")
    if subjects is not None:
        for subj_name, scope in subjects.items():
            if "module" not in scope:
                raise ProtocolError(f"subject {subj_name!r} scope missing required key 'module'")
    return data


def assert_protocol_committed(repo_root, protocol_path, run=subprocess.run) -> None:
    repo_root = Path(repo_root)
    rel = str(Path(protocol_path).resolve().relative_to(repo_root.resolve()))
    # `git show HEAD:rel` is the single source of truth for "committed": it fails
    # both when there is no HEAD yet (a brand-new repo, nothing committed at all)
    # and when the path simply isn't present in the HEAD commit (staged-but-never-
    # committed, or genuinely untracked). A separate `git ls-files` pre-check would
    # wrongly treat a staged-but-uncommitted file as "tracked" and let it fall
    # through to `git show`, which then fails on a missing HEAD with an unrelated
    # git-plumbing error instead of the intended "not committed" message.
    proc = run(["git", "show", f"HEAD:{rel}"], cwd=str(repo_root), capture_output=True, text=True)
    if proc.returncode != 0:
        raise ProtocolError(f"{rel} is not committed; pre-registration requires a committed protocol")
    if proc.stdout != Path(protocol_path).read_text(encoding="utf-8"):
        raise ProtocolError(f"{rel} differs from HEAD; commit the protocol before running")


def run_arm(protocol: dict, arm_name: str, subject_dir, runs_root, module_path: str) -> int:
    """Run one cell. Imports stay local so unit tests of the gate need no providers."""
    from datetime import datetime, timezone

    from crucible.env import SubjectEnv
    from crucible.loop import LoopConfig, harden, oneshot
    from crucible.providers_ext import get_provider
    from crucible.receipts import ReceiptWriter

    arm = protocol["arms"][arm_name]
    tester = get_provider(protocol["tester"]["provider"])
    critic_cfg = arm.get("critic", protocol["tester"])
    critic = tester if critic_cfg == protocol["tester"] else get_provider(critic_cfg["provider"])

    subject_name = Path(subject_dir).name
    subjects = protocol.get("subjects", {})
    if subject_name not in subjects:
        raise ProtocolError(
            f"subject {subject_name!r} is not in protocol['subjects']; the scope must "
            "be frozen in the protocol before this cell can run"
        )
    scope = subjects[subject_name]
    if scope["module"] != module_path:
        raise ProtocolError(
            f"subject {subject_name!r} protocol module {scope['module']!r} does not "
            f"match --module {module_path!r}; the receipt must not disagree with the "
            "frozen config"
        )

    env = SubjectEnv(
        subject_dir=Path(subject_dir),
        tester_provider=tester, tester_model=protocol["tester"]["model"],
        critic_provider=critic, critic_model=critic_cfg["model"],
        module_path=module_path,
        scope=scope,
    )
    # Cell isolation: cells share a subject clone but must each start from the
    # clone's committed state, or the previous cell's accepted crucible_ test
    # files (untracked, since only the arm's own receipt tracks them) leave the
    # clone dirty and preflight correctly refuses to run.
    env.reset_clone()
    head_sha = env.preflight(module_path)

    cfg = LoopConfig(max_rounds=protocol["rounds"]["max_rounds"],
                     dry_rounds=protocol["rounds"]["dry_rounds"], arm=arm_name)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(runs_root) / Path(subject_dir).name / f"{arm_name}-{stamp}"
    writer = ReceiptWriter(run_dir, {
        "subject": str(subject_dir), "module": module_path, "head_sha": head_sha,
        "arm": arm_name, "protocol_version": protocol["protocol_version"],
        "tester_provider": protocol["tester"]["provider"],
        "tester_model": protocol["tester"]["model"],
        "critic_provider": critic_cfg["provider"], "critic_model": critic_cfg["model"],
        "max_rounds": cfg.max_rounds, "dry_rounds": cfg.dry_rounds, "started_at": stamp,
    })
    # rejected-artifact preservation (v3): a rejected or salvaged-away test file lands
    # under this cell's own receipt dir instead of being discarded. Wired before any
    # round runs so round 0's rejection has somewhere to land.
    env.set_artifact_dir(run_dir)
    fn = oneshot if arm["mode"] == "oneshot" else harden
    result = fn(env, cfg, on_round=writer.append)
    writer.finish(result.verdict, result.total_cost_usd, extra={
        "baseline_survivors": result.baseline_survivors,
        "baseline_all_mutants": result.baseline_all_mutants,
        "baseline_counts": result.baseline_counts,
    })
    # Archive accepted generated tests into the run dir so they survive the next reset.
    accepted_dir = run_dir / "accepted"
    accepted_count = 0
    for p in sorted((Path(subject_dir) / "tests").glob("crucible_*_test.py")):
        accepted_dir.mkdir(exist_ok=True)
        shutil.copy2(p, accepted_dir / p.name)
        accepted_count += 1
    print(f"{arm_name} on {Path(subject_dir).name}: verdict={result.verdict} "
          f"cost=${result.total_cost_usd:.4f} receipt={run_dir} (archived {accepted_count} tests)")
    return 3 if result.verdict in ("aborted", "rejected") else 0
