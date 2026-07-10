"""Task 8 pre-registered readouts. Reads experiments/counted.json + the receipts it points at
(via crucible.receipts.load_run), computes per-subject paired 2x2s for H1 (loop-same vs
oneshot) and H2 (loop-cross vs loop-same), pooled exact McNemar in the three PROTOCOL.md
Sec.4-declared views (per-subject, pooled-with-attrition, pooled-without-attrition), kill
counts/rates, cost-per-kill per arm, full-denominator mutation scores, and wrong-oracle drop
counts. Prints plain-ASCII tables to stdout; emits experiments/results.json (every figure,
machine-readable). Stdlib only.

Orientation (PROTOCOL.md Sec.4 honesty rail; matches crucible.cli's own report command):
paired_kills(run_a, run_b) -> (both, a_only, b_only, neither); mcnemar_exact(a_only, b_only)
takes a_only as its first ("b") argument and b_only as its second ("c") argument.
  H1: run_a=loop-same, run_b=oneshot -> b=loop-same-only kills, c=oneshot-only kills;
      H1 favors loop-same when b > c (PROTOCOL.md Sec.5).
  H2: run_a=loop-cross, run_b=loop-same -> b=loop-cross-only kills, c=loop-same-only kills;
      H2 favors loop-cross when b > c (PROTOCOL.md Sec.5).

attrition-risk-ml is never used in a relative-improvement ratio (PROTOCOL.md Sec.3.1/Sec.4) and
is dropped from the pooled-without-attrition view only; its per-subject table and the
pooled-with-attrition view still include it.

graph-guard's counted loop-cross cell (loop-cross-20260710T194101Z) has verdict "rejected"
(round 0, the tester round, failed pristine validation before any test was ever accepted) --
PROTOCOL.md Sec.6 treats a rejected/aborted cell as MISSING data for any metric that needs it,
never as a zero. graph-guard is therefore excluded from H2's per-subject table and from both
pooled H2 views; its H1 cells (oneshot, loop-same) are unaffected and fully counted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crucible.receipts import load_run  # noqa: E402
from crucible.report import mcnemar_exact, paired_kills, summarize  # noqa: E402

ATTRITION_SUBJECT = "attrition-risk-ml"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COUNTED = REPO_ROOT / "experiments" / "counted.json"
DEFAULT_RUNS_ROOT = REPO_ROOT / "experiments" / "runs"
ARMS = ("oneshot", "loop_same", "loop_cross")


def load_counted(counted_path: Path = DEFAULT_COUNTED) -> dict:
    return json.loads(counted_path.read_text(encoding="utf-8"))["subjects"]


def load_counted_runs(counted: dict, runs_root: Path = DEFAULT_RUNS_ROOT) -> dict:
    out = {}
    for subject, cell in counted.items():
        arms = {}
        for arm in ARMS:
            run_dir = runs_root / subject / cell[arm]
            if not (run_dir / "meta.json").exists():
                raise FileNotFoundError(f"{subject}/{arm}: {run_dir} has no meta.json")
            arms[arm] = load_run(run_dir)
        out[subject] = arms
    return out


def dropped_tests(run: dict) -> list[str]:
    """Every round's dropped_tests (per-test wrong-oracle salvage drops, protocol_version 3),
    flattened. A dropped test failed on the pristine module and was never counted as a kill."""
    out: list[str] = []
    for r in run["rounds"]:
        out.extend(r.get("dropped_tests") or [])
    return out


def cell_is_valid(run: dict) -> bool:
    """PROTOCOL.md Sec.6: a rejected/aborted verdict, or no result.json at all, is a missing
    cell for any metric that needs it -- never a zero."""
    result = run.get("result")
    return result is not None and result.get("verdict") not in ("rejected", "aborted")


def per_subject_h1(runs: dict) -> dict:
    out = {}
    for subject, arms in runs.items():
        both, b, c, neither = paired_kills(arms["loop_same"], arms["oneshot"])
        out[subject] = {"both": both, "b_loop_same_only": b, "c_oneshot_only": c,
                         "neither": neither, "p": mcnemar_exact(b, c), "favors_loop_same": b > c}
    return out


def per_subject_h2(runs: dict) -> dict:
    out = {}
    for subject, arms in runs.items():
        if not cell_is_valid(arms["loop_cross"]):
            verdict = (arms["loop_cross"].get("result") or {}).get("verdict", "missing")
            out[subject] = {"excluded": f"loop-cross verdict={verdict}: missing H2 cell, PROTOCOL.md Sec.6"}
            continue
        both, b, c, neither = paired_kills(arms["loop_cross"], arms["loop_same"])
        out[subject] = {"both": both, "b_loop_cross_only": b, "c_loop_same_only": c,
                         "neither": neither, "p": mcnemar_exact(b, c), "favors_loop_cross": b > c}
    return out


def pooled_view(per_subject: dict, b_key: str, c_key: str, include_attrition: bool) -> dict:
    b_total = c_total = 0
    used = []
    for subject, cell in per_subject.items():
        if "excluded" in cell:
            continue
        if not include_attrition and subject == ATTRITION_SUBJECT:
            continue
        b_total += cell[b_key]
        c_total += cell[c_key]
        used.append(subject)
    return {"b": b_total, "c": c_total, "p": mcnemar_exact(b_total, c_total), "subjects": sorted(used)}


def arm_table(runs: dict) -> list[dict]:
    rows = []
    for subject, arms in runs.items():
        for arm in ARMS:
            run = arms[arm]
            s = summarize(run)
            result = run.get("result") or {}
            baseline_all = result.get("baseline_all_mutants")
            baseline_counts = result.get("baseline_counts") or {}
            pre_killed = baseline_counts.get("killed")
            rate = round(100 * s["killed"] / s["baseline_survivors"], 1) if s["baseline_survivors"] else None
            full_score = (round(100 * (pre_killed + s["killed"]) / baseline_all, 1)
                          if baseline_all else None)
            rows.append({
                "subject": subject, "arm": arm, "verdict": s["verdict"],
                "baseline_survivors": s["baseline_survivors"], "killed": s["killed"],
                "kill_rate_pct_of_survivors": rate, "baseline_all_mutants": baseline_all,
                "mutation_score_full_denom_pct": full_score,
                "cost_usd": round(s["cost_usd"], 6),
                "cost_per_kill": (round(s["cost_per_kill"], 4) if s["cost_per_kill"] is not None else None),
                "dropped_tests": dropped_tests(run),
            })
    return rows


def total_spend(runs_root: Path, counted: dict) -> dict:
    counted_dirs = {(subj, cell[arm]) for subj, cell in counted.items() for arm in ARMS}
    counted_total = 0.0
    all_total = 0.0
    n_counted = n_all = 0
    for subject_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        for run_dir in sorted(p for p in subject_dir.iterdir() if p.is_dir()):
            result_path = run_dir / "result.json"
            if not result_path.exists():
                continue
            cost = json.loads(result_path.read_text(encoding="utf-8")).get("total_cost_usd", 0.0)
            all_total += cost
            n_all += 1
            if (subject_dir.name, run_dir.name) in counted_dirs:
                counted_total += cost
                n_counted += 1
    return {"counted_total_usd": round(counted_total, 6), "counted_n_receipts": n_counted,
            "all_receipted_total_usd": round(all_total, 6), "all_n_receipts": n_all,
            "shakeout_total_usd": round(all_total - counted_total, 6)}


def _fmt_p(p: float) -> str:
    return f"{p:.6f}" if p >= 1e-4 else f"{p:.3e}"


def print_report(h1: dict, h2: dict,
                  h1_with: dict, h1_without: dict, h2_with: dict, h2_without: dict,
                  arms: list[dict], spend: dict) -> None:
    print("=" * 78)
    print("H1 per-subject (loop-same vs oneshot): both b(loop-same-only) c(oneshot-only) neither  p")
    for subject, cell in h1.items():
        print(f"  {subject:20s} both={cell['both']:4d} b={cell['b_loop_same_only']:4d} "
              f"c={cell['c_oneshot_only']:4d} neither={cell['neither']:5d}  p={_fmt_p(cell['p'])}  "
              f"favors_loop_same={cell['favors_loop_same']}")
    print(f"H1 pooled-with-attrition:    b={h1_with['b']:4d} c={h1_with['c']:4d}  p={_fmt_p(h1_with['p'])}")
    print(f"H1 pooled-without-attrition: b={h1_without['b']:4d} c={h1_without['c']:4d}  p={_fmt_p(h1_without['p'])}")
    print("-" * 78)
    print("H2 per-subject (loop-cross vs loop-same): both b(loop-cross-only) c(loop-same-only) neither  p")
    for subject, cell in h2.items():
        if "excluded" in cell:
            print(f"  {subject:20s} EXCLUDED: {cell['excluded']}")
            continue
        print(f"  {subject:20s} both={cell['both']:4d} b={cell['b_loop_cross_only']:4d} "
              f"c={cell['c_loop_same_only']:4d} neither={cell['neither']:5d}  p={_fmt_p(cell['p'])}  "
              f"favors_loop_cross={cell['favors_loop_cross']}")
    print(f"H2 pooled-with-attrition:    b={h2_with['b']:4d} c={h2_with['c']:4d}  p={_fmt_p(h2_with['p'])}  subjects={h2_with['subjects']}")
    print(f"H2 pooled-without-attrition: b={h2_without['b']:4d} c={h2_without['c']:4d}  p={_fmt_p(h2_without['p'])}  subjects={h2_without['subjects']}")
    print("-" * 78)
    print(f"{'subject':20s} {'arm':10s} {'verdict':8s} {'base':>5s} {'kill':>5s} {'rate%':>6s} {'cost$':>9s} {'$/kill':>8s} {'dropped':>7s}")
    for r in arms:
        cpk = f"{r['cost_per_kill']:.4f}" if r["cost_per_kill"] is not None else "n/a"
        rate = f"{r['kill_rate_pct_of_survivors']:.1f}" if r["kill_rate_pct_of_survivors"] is not None else "n/a"
        print(f"{r['subject']:20s} {r['arm']:10s} {r['verdict']:8s} {r['baseline_survivors']:5d} "
              f"{r['killed']:5d} {rate:>6s} {r['cost_usd']:9.4f} {cpk:>8s} {len(r['dropped_tests']):7d}")
    print("-" * 78)
    print(f"spend: counted=${spend['counted_total_usd']:.4f} ({spend['counted_n_receipts']} receipts)  "
          f"all-receipted=${spend['all_receipted_total_usd']:.4f} ({spend['all_n_receipts']} receipts)  "
          f"shakeout=${spend['shakeout_total_usd']:.4f}")
    print("=" * 78)


def run_analysis(counted_path: Path = DEFAULT_COUNTED, runs_root: Path = DEFAULT_RUNS_ROOT) -> dict:
    counted = load_counted(counted_path)
    runs = load_counted_runs(counted, runs_root)
    h1 = per_subject_h1(runs)
    h2 = per_subject_h2(runs)
    h1_with = pooled_view(h1, "b_loop_same_only", "c_oneshot_only", include_attrition=True)
    h1_without = pooled_view(h1, "b_loop_same_only", "c_oneshot_only", include_attrition=False)
    h2_with = pooled_view(h2, "b_loop_cross_only", "c_loop_same_only", include_attrition=True)
    h2_without = pooled_view(h2, "b_loop_cross_only", "c_loop_same_only", include_attrition=False)
    arms = arm_table(runs)
    spend = total_spend(runs_root, counted)
    return {
        "counted": counted,
        "h1": {"per_subject": h1, "pooled_with_attrition": h1_with, "pooled_without_attrition": h1_without},
        "h2": {"per_subject": h2, "pooled_with_attrition": h2_with, "pooled_without_attrition": h2_without},
        "arms": arms,
        "spend": spend,
    }


def main(argv=None) -> int:
    results = run_analysis()
    print_report(results["h1"]["per_subject"], results["h2"]["per_subject"],
                 results["h1"]["pooled_with_attrition"], results["h1"]["pooled_without_attrition"],
                 results["h2"]["pooled_with_attrition"], results["h2"]["pooled_without_attrition"],
                 results["arms"], results["spend"])
    out_path = REPO_ROOT / "experiments" / "results.json"
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
