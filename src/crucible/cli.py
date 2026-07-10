"""crucible CLI. Subcommands: oneshot, harden (report arrives in Task 12).

Plain-ASCII output. Exit codes: 0 = clean/dry/cap/oneshot; 3 = aborted/rejected.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from crucible.env import SubjectEnv
from crucible.loop import LoopConfig, harden, oneshot
from crucible.providers_ext import FakeProvider, get_provider
from crucible.receipts import ReceiptWriter


def _provider(name, fake_replies):
    if name == "fake":
        replies = json.loads(Path(fake_replies).read_text()) if fake_replies else []
        return FakeProvider(replies)
    return get_provider(name)


def _cmd_run(args, mode):
    subject = Path(args.subject).resolve()
    tester = _provider(args.tester, args.fake_replies)
    critic = tester if args.critic == args.tester else _provider(args.critic, args.fake_replies)

    env = SubjectEnv(subject_dir=subject, tester_provider=tester, tester_model=args.tester_model,
                     critic_provider=critic, critic_model=args.critic_model,
                     module_path=args.module)
    cfg = LoopConfig(max_rounds=args.rounds, dry_rounds=args.dry_rounds, arm=mode)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.runs_dir) / f"{stamp}-{subject.name}-{mode}"
    writer = ReceiptWriter(run_dir, {
        "subject": str(subject), "module": args.module, "head_sha": env.head_sha(),
        "arm": mode, "tester_model": args.tester_model, "critic_model": args.critic_model,
        "critic_provider": args.critic, "max_rounds": args.rounds,
        "dry_rounds": args.dry_rounds, "started_at": stamp,
    })

    result = oneshot(env, cfg) if mode == "oneshot" else harden(env, cfg)
    for rec in result.rounds:
        writer.append(rec)
    writer.finish(result.verdict, result.total_cost_usd)

    print(f"verdict: {result.verdict}   cost: ${result.total_cost_usd:.4f}")
    for r in result.rounds:
        print(f"  round {r.round} [{r.role:6s}] {r.status:8s} "
              f"kills={len(r.kills):2d} survivors_after={len(r.survivors_after):3d}")
    print(f"receipt: {run_dir}")
    return 3 if result.verdict in ("aborted", "rejected") else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="crucible")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for mode in ("oneshot", "harden"):
        p = sub.add_parser(mode)
        p.add_argument("subject")
        p.add_argument("--module", required=True)
        p.add_argument("--tester", default="anthropic")
        p.add_argument("--tester-model", default="claude-sonnet-5")
        p.add_argument("--critic", default="anthropic")
        p.add_argument("--critic-model", default="claude-sonnet-5")
        p.add_argument("--rounds", type=int, default=5)
        p.add_argument("--dry-rounds", type=int, default=2)
        p.add_argument("--runs-dir", default="runs")
        p.add_argument("--fake-replies", default=None)
    args = parser.parse_args(argv)
    return _cmd_run(args, args.cmd)


if __name__ == "__main__":
    sys.exit(main())
