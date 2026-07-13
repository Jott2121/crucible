#!/usr/bin/env python3
"""$0 model-free validation of the Experiment-B seeded pipeline (PROTOCOL-B, plan step 3).

For each subject in `experiments/protocol-b.json`: reset the clone, run the real
`SubjectEnv.preflight`, then exercise the exact machinery a paid continuation will use --
with a scripted no-op critic and zero model calls:

1. MEASUREMENT DETERMINISM -- the reproduction check's load-bearing assumption. The
   pristine baseline is measured twice back-to-back; any drift between two measurements of
   the identical tree means mutmut is not deterministic on this subject and the frozen-seed
   design cannot run on it (fail loud here, for free, instead of mid-paid-run).
2. CANNED SEED -- the subject's own frozen canary (protocol-b.json) is written and
   validated exactly as a Tester round 0 would be, then measured: this stands in for a real
   seed at $0 (a real killing test, deterministic by construction).
3. FREEZE + COMMIT GATE -- the seed artifact is frozen into a scratch git repo and
   `assert_dir_committed` must refuse it uncommitted, pass it committed, and refuse it
   tampered (drilled on the first subject only; the gate is subject-independent).
4. SEEDED CONTINUATION FOR REAL -- `crucible.loop.seeded_run` runs against the real clone
   and real mutmut with the frozen expectations from step 2: its internal baseline and
   post-round-0 reproduction checks are live drills of the §4 gates (each is measurement
   determinism sample #2 for its phase), and its critic rounds call a scripted provider
   that returns a harmless passing test, so the loop runs to a real verdict (expected:
   `dry`, or `clean` if the canary killed everything) at exactly $0.00.
5. REPRODUCTION-CHECK REFUSAL -- on the first subject only, seeded_run is re-run with a
   deliberately wrong frozen survivor set and must raise ReproductionMismatch: proof the
   gate fires against a real measurement, not only in unit tests.

Never touches experiments/seeds/ or experiments/runs-b/ (scratch tempdirs only). Never
constructs a paid provider. Exit 0 = every check passed on every subject.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from oracle_gate.providers import Usage  # noqa: E402

from crucible.env import SubjectEnv  # noqa: E402
from crucible.experiment_b import ProtocolBError, assert_dir_committed, load_protocol_b  # noqa: E402
from crucible.loop import LoopConfig, ReproductionMismatch, seeded_run  # noqa: E402

NOOP_TEST = "```python\ndef test_validate_b_noop():\n    assert True\n```"


class ScriptedNoOpProvider:
    """Returns a harmless passing test; priced model name so cost math runs ($0 usage)."""

    name = "scripted-noop"
    billing = "fake"  # honest label; this script never enters the paid runner

    def complete_with_usage(self, system, user, model="claude-sonnet-5"):
        return NOOP_TEST, Usage(0, 0)


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")
    raise SystemExit(2)


def _env_for(subject_dir: Path, module: str, scope: dict) -> SubjectEnv:
    provider = ScriptedNoOpProvider()
    return SubjectEnv(subject_dir=subject_dir,
                      tester_provider=provider, tester_model="claude-sonnet-5",
                      critic_provider=provider, critic_model="claude-sonnet-5",
                      module_path=module, scope=scope)


def _freeze_to_scratch(scratch_repo: Path, subject: str, text: str, seed: dict) -> Path:
    rep_dir = scratch_repo / "seeds" / subject / "rep1"
    rep_dir.mkdir(parents=True)
    (rep_dir / "seed_test.py").write_text(text, encoding="utf-8")
    (rep_dir / "seed.json").write_text(json.dumps(seed, indent=2), encoding="utf-8")
    return rep_dir


def _git(repo: Path, *args) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def validate_subject(name: str, scope: dict, subjects_root: Path, protocol: dict,
                     drill_gates: bool) -> None:
    subject_dir = subjects_root / name
    module = scope["module"]
    print(f"\n=== {name} ({module}) ===")
    env = _env_for(subject_dir, module, scope)
    env.reset_clone()
    head = env.preflight(module)
    print(f"  preflight ok @ {head[:12]}")

    # 1. baseline determinism, the assumption everything else stands on
    pre1 = env.measure()
    pre2 = env.measure()
    if set(pre1.survivors) != set(pre2.survivors) or pre1.all_mutants != pre2.all_mutants:
        _fail(f"baseline NOT deterministic: run1 {len(pre1.survivors)} survivors / "
              f"{pre1.all_mutants} mutants, run2 {len(pre2.survivors)} / {pre2.all_mutants}")
    print(f"  baseline deterministic: {len(pre1.survivors)} survivors of "
          f"{pre1.all_mutants} mutants (measured twice, identical)")

    # 2. canned seed = the subject's own frozen canary
    canary = scope.get("canary")
    if not canary:
        _fail("subject has no canary in protocol-b.json; nothing to use as a canned seed")
    path = env.write_test_file(0, "validate-b", canary)
    dropped = env.validate(path)
    if dropped:
        _fail(f"canary was salvage-dropped at validation: {dropped}")
    post = env.measure()
    killed = len(set(pre1.survivors)) - len(set(post.survivors))
    print(f"  canned seed accepted: canary killed {killed}, {len(post.survivors)} remain")
    frozen_text = (subject_dir / path).read_text(encoding="utf-8")

    # 3. freeze + commit gate (drilled once; gate logic is subject-independent)
    seed = {"subject": name, "rep": 1, "module": module, "head_sha": head, "draw": 1,
            "baseline_survivors": list(pre1.survivors),
            "baseline_all_mutants": pre1.all_mutants,
            "baseline_counts": dict(pre1.counts),
            "post_survivors": list(post.survivors),
            "post_counts": dict(post.counts),
            "test_sha256": hashlib.sha256(frozen_text.encode("utf-8")).hexdigest(),
            "provenance": {"model": "validate-b-canary", "prompt_sha256": "0" * 64,
                           "usage_in": 0, "usage_out": 0, "cost_usd": 0.0,
                           "dropped_tests": [], "generated_at": "validate-b"}}
    if drill_gates:
        with tempfile.TemporaryDirectory() as scratch:
            scratch_repo = Path(scratch)
            _git(scratch_repo, "init", "-q")
            rep_dir = _freeze_to_scratch(scratch_repo, name, frozen_text, seed)
            try:
                assert_dir_committed(scratch_repo, rep_dir)
                _fail("commit gate PASSED an uncommitted seed dir")
            except ProtocolBError:
                print("  commit gate refuses uncommitted seed: ok")
            _git(scratch_repo, "add", "-A")
            _git(scratch_repo, "-c", "user.email=v@b", "-c", "user.name=validate-b",
                 "commit", "-qm", "freeze")
            assert_dir_committed(scratch_repo, rep_dir)
            print("  commit gate passes committed seed: ok")
            (rep_dir / "seed_test.py").write_text(frozen_text + "# tampered\n",
                                                  encoding="utf-8")
            try:
                assert_dir_committed(scratch_repo, rep_dir)
                _fail("commit gate PASSED a tampered seed dir")
            except ProtocolBError:
                print("  commit gate refuses tampered seed: ok")

    # 4. the real seeded continuation, $0: internal baseline + post reproduction
    #    checks are live drills of PROTOCOL-B §4 against real measurements
    env2 = _env_for(subject_dir, module, scope)
    env2.reset_clone()
    env2.preflight(module)
    cfg = LoopConfig(max_rounds=protocol["rounds"]["max_rounds"],
                     dry_rounds=protocol["rounds"]["dry_rounds"], arm="validate-b")
    result = seeded_run(env2, cfg, frozen_text, seed["baseline_survivors"],
                        seed["post_survivors"], seed_model="validate-b-canary",
                        seed_prompt_sha256="0" * 64)
    if result.verdict not in ("dry", "clean", "cap"):
        _fail(f"seeded continuation verdict {result.verdict!r}, expected dry/clean/cap")
    if result.total_cost_usd != 0.0:
        _fail(f"seeded continuation cost ${result.total_cost_usd} != $0")
    print(f"  seeded continuation ran clean: verdict={result.verdict}, "
          f"{len(result.rounds)} rounds, $0.00 (reproduction checks passed live)")

    # 5. the reproduction check must FIRE against a real measurement (drilled once)
    if drill_gates and not seed["post_survivors"]:
        print("  note: canary killed everything; wrong-frozen-state drill skipped "
              "(an empty set minus one is still empty)")
    if drill_gates and seed["post_survivors"]:
        env3 = _env_for(subject_dir, module, scope)
        env3.reset_clone()
        env3.preflight(module)
        wrong_post = list(seed["post_survivors"])[1:]  # deliberately wrong frozen state
        try:
            seeded_run(env3, cfg, frozen_text, seed["baseline_survivors"], wrong_post)
            _fail("reproduction check did NOT fire on a wrong frozen survivor set")
        except ReproductionMismatch as exc:
            print(f"  reproduction check fires on wrong frozen state: ok ({str(exc)[:60]}...)")

    env_final = _env_for(subject_dir, module, scope)
    env_final.reset_clone()
    print(f"  {name}: ALL CHECKS PASSED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subjects-root", default=str(Path.home() / "crucible-subjects"))
    parser.add_argument("--only", nargs="*", default=None,
                        help="subset of subjects (default: all in protocol-b.json)")
    args = parser.parse_args()

    protocol = load_protocol_b(REPO / "experiments" / "protocol-b.json")
    names = args.only or list(protocol["subjects"])
    unknown = set(names) - set(protocol["subjects"])
    if unknown:
        print(f"unknown subjects: {sorted(unknown)}")
        return 2
    for i, name in enumerate(names):
        validate_subject(name, protocol["subjects"][name], Path(args.subjects_root),
                         protocol, drill_gates=(i == 0))
    print(f"\nvalidate_b: ALL {len(names)} SUBJECTS PASSED -- the seeded pipeline is "
          "mechanically sound at $0; Phase A may be proposed to the operator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
