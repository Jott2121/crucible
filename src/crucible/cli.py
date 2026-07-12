"""crucible CLI. Subcommands: oneshot, harden, report, experiment, scope.

Plain-ASCII output. Exit codes: 0 = clean/dry/cap/oneshot; 2 = harden/oneshot
refused before any work (e.g. the named module does not exist in the subject);
3 = aborted/rejected; 4 = scope's canary probe refused -- a RuntimeError or
FileNotFoundError from detect/apply/canary_probe (single refusal path, printed
as "REFUSING: {exc}", no traceback leak) or a proven kills-did-not-increase
verdict (unproven scope, refuse before spending any model tokens). A WAIVED
verdict (the existing suite already kills under this scope -- 2026-07-11
owner-approved amendment) exits 0, not 4.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import crucible
from crucible import scope as scope_mod
from crucible.env import SubjectEnv
from crucible.loop import LoopConfig, harden, oneshot
from crucible.providers_ext import FakeProvider, get_provider
from crucible.receipts import ReceiptWriter


def _provider(name, fake_replies):
    if name == "fake":
        replies = json.loads(Path(fake_replies).read_text()) if fake_replies else []
        return FakeProvider(replies)
    return get_provider(name)


def _derive_run_scope(subject: Path, module: str) -> dict:
    """Derive the run scope the SAME way `crucible scope` does, so harden's
    preflight writes the byte-identical [tool.mutmut] (+ conftest shim) that
    scope's canary validated -- never a bare source_paths that silently drops
    also_copy/pytest_args/the src-shim (see env.py preflight's scope=
    handling). On src-layouts, also thread the bare-module import_hint into
    the tester/critic prompts (env.py reads scope["import_hint"]) --
    generated tests import `mod`, never `src.mod` (the sandbox path the shim
    creates; closes the ledger's src-layout inefficiency residual)."""
    plan = scope_mod.detect(subject, module)
    run_scope: dict = {"also_copy": plan.also_copy,
                       "pytest_args": plan.pytest_args or None}
    if plan.needs_src_shim:
        run_scope["extra_files"] = {"conftest.py": scope_mod.SRC_SHIM}
        modname = module[:-3].replace("/", ".")
        if modname.startswith("src."):
            modname = modname[len("src."):]
        run_scope["import_hint"] = (
            f"Import the module under test as `{modname}` -- the src/ prefix "
            "is not importable in the test environment.")
    return run_scope


def _cmd_run(args, mode):
    subject = Path(args.subject).resolve()

    # Gate-7 live defect 1: a runs-dir INSIDE the subject repo makes crucible's
    # own receipt writes (meta.json, receipt.jsonl) show up as untracked files
    # in the subject clone and trip crucible's own add-only guardrail mid-run
    # ('?? .crucible-runs/...meta.json' rejected round 0 on the first live
    # run). Refuse fail-loud before preflight or any model call.
    runs_dir = Path(args.runs_dir).resolve()
    if runs_dir.is_relative_to(subject):
        print(f"ERROR: --runs-dir {runs_dir} is inside the subject repo {subject}; "
              "crucible's receipt writes would trip its own add-only guardrail "
              "mid-run. Use a runs dir outside the repo, e.g. ~/.crucible-runs/<repo-name>")
        return 2

    tester = _provider(args.tester, args.fake_replies)
    critic = tester if args.critic == args.tester else _provider(args.critic, args.fake_replies)

    try:
        run_scope = _derive_run_scope(subject, args.module)
    except FileNotFoundError as exc:
        # clean one-line refusal naming the missing module; never a traceback
        print(f"ERROR: {exc}")
        return 2

    env = SubjectEnv(subject_dir=subject, tester_provider=tester, tester_model=args.tester_model,
                     critic_provider=critic, critic_model=args.critic_model,
                     module_path=args.module, scope=run_scope)
    cfg = LoopConfig(max_rounds=args.rounds, dry_rounds=args.dry_rounds, arm=mode)

    # hard stop (dirty clone / red suite / non-git dir) before any token is spent;
    # also writes+commits the [tool.mutmut] scope for --module inside the clone
    head_sha = env.preflight(module_path=args.module)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = runs_dir / f"{stamp}-{subject.name}-{mode}"
    writer = ReceiptWriter(run_dir, {
        "subject": str(subject), "module": args.module, "head_sha": head_sha,
        "arm": mode, "tester_model": args.tester_model, "critic_model": args.critic_model,
        "tester_provider": args.tester, "critic_provider": args.critic,
        "tester_billing": getattr(tester, "billing", "api"),
        "critic_billing": getattr(critic, "billing", "api"),
        "lean_isolation": getattr(tester, "isolation_name", "ambient"),
        "max_rounds": args.rounds, "dry_rounds": args.dry_rounds, "started_at": stamp,
        "crucible_version": crucible.__version__,
        "oracle_gate_version": importlib.metadata.version("oracle-gate"),
        "mutmut_version": importlib.metadata.version("mutmut"),
    })
    # Gate-7 live defect 3: rejected/salvaged test files are evidence, never
    # discarded (spec posture). run_arm already wires this; the CLI path must
    # too, before any round runs so a round-0 rejection has somewhere to land.
    env.set_artifact_dir(run_dir)

    run_fn = oneshot if mode == "oneshot" else harden
    result = run_fn(env, cfg, on_round=writer.append)
    writer.finish(result.verdict, result.total_cost_usd, extra={
        "baseline_survivors": result.baseline_survivors,
        "baseline_all_mutants": result.baseline_all_mutants,
        "baseline_counts": result.baseline_counts,
    })

    print(f"verdict: {result.verdict}   cost: ${result.total_cost_usd:.4f}")
    for r in result.rounds:
        print(f"  round {r.round} [{r.role:6s}] {r.status:8s} "
              f"kills={len(r.kills):2d} survivors_after={len(r.survivors_after):3d}")
    print(f"receipt: {run_dir}")
    return 3 if result.verdict in ("aborted", "rejected") else 0


def _cmd_report(args) -> int:
    from crucible.receipts import load_run
    from crucible.report import mcnemar_exact, paired_kills, summarize

    runs = [load_run(p) for p in args.runs]
    for r in runs:
        s = summarize(r)
        cpk = f"${s['cost_per_kill']:.4f}" if s["cost_per_kill"] is not None else "n/a"
        # billing rides on every cost figure (spec §4: never silently mix
        # metered API spend with Max-plan shadow prices -- a $ number without
        # its billing basis is exactly that silent mix)
        print(f"{s['arm']:8s} verdict={s['verdict']:6s} baseline={s['baseline_survivors']:3d} "
              f"killed={s['killed']:3d} cost=${s['cost_usd']:.4f} cost/kill={cpk} "
              f"billing={s['billing']} lean={s['lean_isolation']}")
    if len(runs) == 2:
        both, a_only, b_only, neither = paired_kills(runs[0], runs[1])
        p = mcnemar_exact(a_only, b_only)
        print(f"paired 2x2: both={both} a_only={a_only} b_only={b_only} neither={neither}")
        print(f"McNemar exact p = {p:.6f}")
    return 0


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
    rp = sub.add_parser("report")
    rp.add_argument("runs", nargs="+")
    ep = sub.add_parser("experiment")
    ep.add_argument("protocol")
    ep.add_argument("--arm", required=True)
    ep.add_argument("--subject", required=True)
    ep.add_argument("--module", required=True)
    ep.add_argument("--runs-dir", default="experiments/runs")
    sp = sub.add_parser(
        "scope",
        help="detect+write the mutmut scope for one module, then canary-prove it "
             "($0, no model calls); refuses what it cannot validate",
        description="Detect the subject's layout, write the [tool.mutmut] scope for "
                    "one module, and prove it with a $0 canary probe before any model "
                    "spend. Honest limitation (spec section 6): the heuristics target "
                    "well-formed Python repos with pytest; a repo the gate cannot "
                    "validate is refused, not guessed (exit 4 with the reason).",
    )
    sp.add_argument("subject")
    sp.add_argument("--module", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "report":
        return _cmd_report(args)
    if args.cmd == "experiment":
        from crucible.experiment import assert_protocol_committed, load_protocol, run_arm
        # repo root = cwd; the protocol must live in the crucible repo checkout
        # (this command must be run from the crucible repo root, where experiments/ lives)
        assert_protocol_committed(Path.cwd(), Path(args.protocol))
        protocol = load_protocol(args.protocol)
        return run_arm(protocol, args.arm, args.subject, args.runs_dir, args.module)
    if args.cmd == "scope":
        subject = Path(args.subject).resolve()
        try:
            plan = scope_mod.detect(subject, args.module)
            scope_mod.apply(subject, plan)
            for note in plan.notes:
                print(f"note: {note}")
            v = scope_mod.canary_probe(subject, args.module)
        except (RuntimeError, FileNotFoundError) as exc:
            # FileNotFoundError = detect's missing-module refusal; same single
            # refusal path as RuntimeError, never a raw traceback
            print(f"REFUSING: {exc}")
            return 4
        print(f"scope written: also_copy={plan.also_copy} pytest_args={plan.pytest_args} "
              f"shim={plan.needs_src_shim}")
        if v.waived:
            print(f"canary: WAIVED (existing suite kills {v.kills_before} of {v.mutants} "
                  "mutants; collection proven)")
            return 0
        status = "KILLS" if v.passed else "NO-KILLS"
        print(f"canary: {status} ({v.kills_before} -> {v.kills_after} of {v.mutants} mutants)")
        if not v.passed:
            print("REFUSING: a fresh test file is not being collected under this scope; "
                  "fix the scope before spending any model tokens")
            return 4
        return 0
    return _cmd_run(args, args.cmd)


if __name__ == "__main__":
    sys.exit(main())
