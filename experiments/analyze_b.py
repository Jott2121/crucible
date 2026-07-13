"""PROTOCOL-B pre-registered readouts (Sec.5 metrics, Sec.6 analysis rules).

Reads the frozen seeds (experiments/seeds/<subject>/rep<k>/seed.json) and the Phase-B
receipts (experiments/runs-b/<subject>/<arm>-rep<k>-*/), computes per-replicate paired
deltas and the pre-registered effect sizes with bootstrap intervals, prints plain-ASCII
tables, and emits experiments/results-b.json. Stdlib only.

Pre-registered structure this file implements mechanically:

- Unit of analysis = the replicate (Sec.2). Per replicate: k0 (the frozen round 0's own
  kills), ksame/kcross (loop totals), Dsame/Dcross (incremental kills, >= 0 by
  construction), rho_same/rho_cross (incremental kill RATE among the frozen post-round-0
  survivors; undefined when |S|=0 -- such replicates are counted, reported, included in
  count summaries, excluded from rate averages, Sec.5).
- E-B1 primary readout: per-subject mean Dsame / rho_same with 95% percentile bootstrap
  intervals over replicates; pooled = UNWEIGHTED mean of subject means with a
  subject-level cluster bootstrap (Sec.6). RNG seed 20260713 and 10,000 draws are frozen
  in protocol-b.json's analysis block -- this file READS them from there rather than
  declaring its own, so the frozen protocol stays the single source of truth.
- E-B2 pilot: within-replicate D = Dcross - Dsame, same reporting, no verdict (Sec.6).
- NO pooled-per-mutant McNemar as a confirmatory statistic (Sec.6).
- Per-estimand replicate validity (Sec.6): E-B1 needs a valid seed + valid loop-same;
  E-B2 needs a valid seed + BOTH valid loop continuations. Every reported estimate states
  its replicate composition. Missing replicates are reported, never imputed.
- Cell validity mirrors Experiment 1's Sec.6 guard: verdict in (clean, dry, cap, oneshot)
  counts; invalid / aborted / crashed (no result.json) cells are missing, never zeros.
  Cells are matched to the CURRENT seed via meta.json's seed.test_sha256 (a retired
  seed's receipts are DEVIATIONS history, PROTOCOL-B Sec.4).
- Cost per incremental kill (Sec.5): continuation cost / Delta, only where Delta >= 1;
  seed spend reported separately and never allocated to continuations.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = REPO_ROOT / "experiments" / "protocol-b.json"
DEFAULT_SEEDS = REPO_ROOT / "experiments" / "seeds"
DEFAULT_RUNS_B = REPO_ROOT / "experiments" / "runs-b"
VALID_VERDICTS = ("clean", "dry", "cap", "oneshot")
LOOP_ARMS = ("loop-same", "loop-cross")


def load_analysis_params(protocol_path: Path = DEFAULT_PROTOCOL) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    return {"k": protocol["replicates"]["k"],
            "subjects": sorted(protocol["subjects"]),
            "bootstrap_draws": protocol["analysis"]["bootstrap_draws"],
            "rng_seed": protocol["analysis"]["rng_seed"]}


def load_seed(seeds_root: Path, subject: str, rep: int) -> dict | None:
    p = seeds_root / subject / f"rep{rep}" / "seed.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def find_cell(runs_root: Path, subject: str, arm: str, rep: int, seed_sha: str) -> dict:
    """The cell for (subject, arm, rep) under the CURRENT seed. Returns
    {status: 'valid'|'missing', ...}; anything not validly scored
    (invalid / aborted / crashed / wrong-seed) leaves the cell missing for
    metrics while its receipted spend stays visible. TWO validly scored dirs
    under the same seed cannot legitimately exist (the runner's Sec.8 gate) --
    the analyzer is the last gate before printed numbers, so that state fails
    loud instead of silently selecting a receipt (the selection failure class
    the paper autopsies)."""
    cell_dirs = sorted((runs_root / subject).glob(f"{arm}-rep{rep}-*"))
    spent = 0.0
    chosen = None
    statuses = []
    for d in cell_dirs:
        meta_p, result_p = d / "meta.json", d / "result.json"
        if meta_p.exists():
            meta_sha = json.loads(meta_p.read_text(encoding="utf-8")).get("seed", {}).get("test_sha256")
            if meta_sha is not None and meta_sha != seed_sha:
                continue  # retired seed's receipts: out of scope here (Sec.4);
                # their spend is still counted by spend_summary's all-receipts walk
        receipt = d / "receipt.jsonl"
        if receipt.exists():
            for line in receipt.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    spent += json.loads(line).get("cost_usd", 0.0)
        if not result_p.exists():
            statuses.append("crashed")
            continue
        result = json.loads(result_p.read_text(encoding="utf-8"))
        if result.get("verdict") in VALID_VERDICTS:
            if chosen is not None:
                raise ValueError(
                    f"{subject}/{arm}/rep{rep}: TWO validly scored receipts under the "
                    f"same seed ({chosen[0].name} and {d.name}) -- impossible via the "
                    "runner's Sec.8 gate, so this is a protocol violation; refusing to "
                    "select one silently. Resolve via DEVIATIONS.md before analysis.")
            chosen = (d, result)
            statuses.append(result["verdict"])
        else:
            statuses.append(result.get("verdict", "unknown"))
    if chosen is None:
        return {"status": "missing", "attempt_statuses": statuses, "spent_usd": round(spent, 6)}
    d, result = chosen
    rounds = [json.loads(l) for l in (d / "receipt.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    killed = sum(len(r.get("kills") or []) for r in rounds)
    round0 = next((r for r in rounds if r.get("round") == 0), None)
    baseline_counts = result.get("baseline_counts") or {}
    return {"status": "valid", "dir": d.name, "verdict": result["verdict"],
            "killed_total": killed, "cost_usd": result.get("total_cost_usd", 0.0),
            "round0_kills": len(round0.get("kills") or []) if round0 else None,
            "critic_rounds": sum(1 for r in rounds if r.get("role") == "critic"),
            "rejected_rounds": sum(1 for r in rounds if r.get("status") == "rejected"),
            "baseline_all_mutants": result.get("baseline_all_mutants"),
            "pre_killed": baseline_counts.get("killed"),
            "spent_usd": round(spent, 6), "attempt_statuses": statuses}


def replicate_rows(params: dict, seeds_root: Path, runs_root: Path) -> list[dict]:
    rows = []
    for subject in params["subjects"]:
        for rep in range(1, params["k"] + 1):
            seed = load_seed(seeds_root, subject, rep)
            if seed is None:
                rows.append({"subject": subject, "rep": rep, "seed": "missing"})
                continue
            n_base = len(seed["baseline_survivors"])
            n_s = len(seed["post_survivors"])
            k0 = n_base - n_s
            row = {"subject": subject, "rep": rep, "seed": "ok",
                   "n_base": n_base, "s": n_s, "k0": k0}
            for arm in LOOP_ARMS:
                cell = find_cell(runs_root, subject, arm, rep, seed["test_sha256"])
                key = arm.replace("-", "_")
                row[key] = cell
                if cell["status"] != "valid":
                    continue
                # free integrity assertion: the reproduction check guarantees the
                # seeded round 0 killed exactly k0; a receipt disagreeing with its
                # own seed is corrupt and must never reach a printed number
                if cell["round0_kills"] is not None and cell["round0_kills"] != k0:
                    raise ValueError(
                        f"{subject}/{arm}/rep{rep}: receipt round-0 kills "
                        f"{cell['round0_kills']} != seed-derived k0 {k0}; receipt and "
                        "frozen seed disagree -- refusing to analyze corrupt data")
                delta = cell["killed_total"] - k0
                if delta < 0:
                    # unreachable from this instrument (Sec.4 resurrection gate);
                    # never averaged in as a negative loop effect
                    cell["status"] = "invalid-negative-delta"
                    row.setdefault("instrument_flags", []).append(
                        f"{arm}: delta {delta} < 0 -- instrument failure (Sec.4)")
                    continue
                row[f"{key}_delta"] = delta
                row[f"{key}_rho"] = (delta / n_s) if n_s > 0 else None
                row[f"{key}_cost_per_delta"] = (
                    round(cell["cost_usd"] / delta, 6) if delta >= 1 else None)
                if cell["baseline_all_mutants"] and cell["pre_killed"] is not None:
                    # lesson 0018: the full-denominator score, alongside the
                    # survivor-relative rate (Sec.5 "both denominators")
                    row[f"{key}_full_score_pct"] = round(
                        100 * (cell["pre_killed"] + cell["killed_total"])
                        / cell["baseline_all_mutants"], 1)
            if (row.get("loop_same", {}).get("status") == "valid"
                    and row.get("loop_cross", {}).get("status") == "valid"):
                row["d_cross_minus_same"] = row["loop_cross_delta"] - row["loop_same_delta"]
                if n_s > 0:
                    # Sec.5's E-B2 rate analogue: the WITHIN-REPLICATE paired rate
                    # gap (undefined at |S|=0, same exclusion rule as the rates)
                    row["rho_gap"] = row["loop_cross_rho"] - row["loop_same_rho"]
            rows.append(row)
    return rows


def bootstrap_ci(values: list[float], rng: random.Random, draws: int) -> dict | None:
    """95% percentile bootstrap of the mean. Deterministic given the frozen RNG."""
    if not values:
        return None
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return {"mean": round(sum(values) / n, 4), "n": n,
            "lo95": round(means[int(0.025 * draws)], 4),
            "hi95": round(means[int(0.975 * draws) - 1], 4)}


def estimand(rows: list[dict], value_key: str, needed: tuple[str, ...],
             params: dict, rng: random.Random) -> dict:
    """One pre-registered readout: per-subject bootstrap over replicates + pooled
    unweighted-mean-of-subject-means with subject-cluster bootstrap. A replicate
    contributes only when ALL its needed cells are valid AND the value is defined
    (rates are None when |S|=0 -- excluded from rate averages, counted, Sec.5)."""
    draws = params["bootstrap_draws"]
    per_subject = {}
    subject_means = []
    composition = {}
    undefined_rate_reps = 0
    for subject in params["subjects"]:
        values, used = [], []
        for row in rows:
            if row["subject"] != subject or row.get("seed") != "ok":
                continue
            if any(row.get(k.replace("-", "_"), {}).get("status") != "valid" for k in needed):
                continue
            v = row.get(value_key)
            if v is None:
                undefined_rate_reps += 1
                continue
            values.append(float(v))
            used.append(row["rep"])
        per_subject[subject] = {"ci": bootstrap_ci(values, rng, draws), "replicates": used}
        composition[subject] = used
        if values:
            subject_means.append(sum(values) / len(values))
    pooled = None
    pooled_subjects = [s for s in params["subjects"] if composition.get(s)]
    if subject_means:
        n = len(subject_means)
        means = sorted(sum(subject_means[rng.randrange(n)] for _ in range(n)) / n
                       for _ in range(draws))
        pooled = {"mean": round(sum(subject_means) / n, 4), "n_subjects": n,
                  "subjects": pooled_subjects,
                  "lo95": round(means[int(0.025 * draws)], 4),
                  "hi95": round(means[int(0.975 * draws) - 1], 4)}
    return {"per_subject": per_subject, "pooled_unweighted_subject_means": pooled,
            "replicate_composition": composition,
            "rate_undefined_replicates_excluded": undefined_rate_reps}


def spend_summary(rows: list[dict], seeds_root: Path, runs_root: Path) -> dict:
    """Sec.10 posture: EVERY receipted dollar visible. Attribution (per arm, per
    current seed) can miss retired-seed receipts and cells whose seed is missing;
    the all-receipts walk cannot -- the gap is reported, never silently dropped."""
    # summed from receipt.jsonl lines, NOT result.json totals: a draw that
    # crashed after billing has receipted rounds but no result.json (the same
    # class Experiment 1 disclosed as its known $0.21 gap). For finished draws
    # the two are equal by construction, so this is strictly more complete.
    seed_total = 0.0
    for receipt in sorted(seeds_root.glob("*/rep*/draws/*/receipt.jsonl")):
        for line in receipt.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seed_total += json.loads(line).get("cost_usd", 0.0)
    cont = {"loop_same": 0.0, "loop_cross": 0.0}
    for row in rows:
        for key in cont:
            cell = row.get(key)
            if isinstance(cell, dict):
                cont[key] += cell.get("spent_usd", 0.0)
    runs_b_all = 0.0
    for receipt in sorted(runs_root.glob("*/*/receipt.jsonl")):
        for line in receipt.read_text(encoding="utf-8").splitlines():
            if line.strip():
                runs_b_all += json.loads(line).get("cost_usd", 0.0)
    attributed = sum(cont.values())
    return {"seed_draws_usd": round(seed_total, 6),
            "loop_same_usd": round(cont["loop_same"], 6),
            "loop_cross_usd": round(cont["loop_cross"], 6),
            "runs_b_all_receipted_usd": round(runs_b_all, 6),
            "runs_b_unattributed_usd": round(runs_b_all - attributed, 6),
            "all_receipted_total_usd": round(seed_total + runs_b_all, 6)}


def descriptives(rows: list[dict]) -> dict:
    """Sec.5's declared descriptives, per arm: verdict distribution and
    mean_critic_rounds are over VALID cells (invalid/aborted/crashed attempts
    stay visible per-row in attempt_statuses); rejected-round totals across the
    same valid cells. Full-denominator scores ride on each replicate row."""
    out = {}
    for key in ("loop_same", "loop_cross"):
        verdicts: dict[str, int] = {}
        critic_rounds = []
        rejected = 0
        for row in rows:
            cell = row.get(key)
            if not isinstance(cell, dict) or cell.get("status") != "valid":
                continue
            verdicts[cell["verdict"]] = verdicts.get(cell["verdict"], 0) + 1
            critic_rounds.append(cell["critic_rounds"])
            rejected += cell["rejected_rounds"]
        out[key] = {"verdicts": verdicts,
                    "valid_cells": len(critic_rounds),
                    "mean_critic_rounds": (round(sum(critic_rounds) / len(critic_rounds), 2)
                                           if critic_rounds else None),
                    "rejected_rounds_total": rejected}
    return out


def run_analysis(protocol_path: Path = DEFAULT_PROTOCOL, seeds_root: Path = DEFAULT_SEEDS,
                 runs_root: Path = DEFAULT_RUNS_B) -> dict:
    params = load_analysis_params(protocol_path)
    rng = random.Random(params["rng_seed"])
    rows = replicate_rows(params, seeds_root, runs_root)
    # RNG consumption order is fixed: the five estimands below, in this order,
    # subjects sorted -- so every run of this file reproduces identical intervals.
    eb1_delta = estimand(rows, "loop_same_delta", ("loop-same",), params, rng)
    eb1_rho = estimand(rows, "loop_same_rho", ("loop-same",), params, rng)
    eb2_d = estimand(rows, "d_cross_minus_same", ("loop-same", "loop-cross"), params, rng)
    eb2_rho_gap = estimand(rows, "rho_gap", ("loop-same", "loop-cross"), params, rng)
    eb2_rho_cross = estimand(rows, "loop_cross_rho", ("loop-same", "loop-cross"), params, rng)
    return {"params": params, "replicates": rows,
            "eb1": {"delta_same": eb1_delta, "rho_same": eb1_rho},
            "eb2": {"d_cross_minus_same": eb2_d, "rho_gap": eb2_rho_gap,
                    "rho_cross": eb2_rho_cross},
            "descriptives": descriptives(rows),
            "spend": spend_summary(rows, seeds_root, runs_root)}


def _fmt_ci(ci: dict | None) -> str:
    if ci is None:
        return "n/a"
    return f"{ci['mean']:7.3f} [{ci['lo95']:7.3f}, {ci['hi95']:7.3f}] n={ci.get('n', ci.get('n_subjects'))}"


def print_report(results: dict) -> None:
    print("=" * 96)
    print("PROTOCOL-B replicate table: k0=frozen round-0 kills, S=frozen survivors, "
          "D=incremental kills, rho=D/S")
    print(f"{'subject':13s} {'rep':>3s} {'base':>5s} {'S':>4s} {'k0':>4s} "
          f"{'Dsame':>6s} {'rho_s':>6s} {'Dcross':>7s} {'rho_c':>6s} {'D(c-s)':>7s} "
          f"{'same':>6s} {'cross':>6s}")
    for row in results["replicates"]:
        if row.get("seed") != "ok":
            print(f"{row['subject']:13s} {row['rep']:3d}  SEED MISSING")
            continue
        def v(key, fmt="{:d}"):
            val = row.get(key)
            return fmt.format(val) if val is not None else "-"
        same = row.get("loop_same", {})
        cross = row.get("loop_cross", {})
        print(f"{row['subject']:13s} {row['rep']:3d} {row['n_base']:5d} {row['s']:4d} "
              f"{row['k0']:4d} {v('loop_same_delta'):>6s} {v('loop_same_rho', '{:.2f}'):>6s} "
              f"{v('loop_cross_delta'):>7s} {v('loop_cross_rho', '{:.2f}'):>6s} "
              f"{v('d_cross_minus_same'):>7s} "
              f"{same.get('verdict', same.get('status', '?')):>6s} "
              f"{cross.get('verdict', cross.get('status', '?')):>6s}")
    print("-" * 96)
    print("E-B1 (causal, primary): same-lineage critic rounds' incremental effect over the frozen round 0")
    print(f"  pooled Dsame  (unweighted subject means): {_fmt_ci(results['eb1']['delta_same']['pooled_unweighted_subject_means'])}")
    print(f"  pooled rho_same:                          {_fmt_ci(results['eb1']['rho_same']['pooled_unweighted_subject_means'])}")
    for subj, cell in results["eb1"]["delta_same"]["per_subject"].items():
        rho = results["eb1"]["rho_same"]["per_subject"][subj]["ci"]
        print(f"    {subj:13s} Dsame {_fmt_ci(cell['ci'])}   rho {_fmt_ci(rho)}   reps={cell['replicates']}")
    print("E-B2 (pilot, no verdict): cross-vs-same within-replicate difference")
    print(f"  pooled D(cross-same):   {_fmt_ci(results['eb2']['d_cross_minus_same']['pooled_unweighted_subject_means'])}")
    print(f"  pooled rho-gap (c-s):   {_fmt_ci(results['eb2']['rho_gap']['pooled_unweighted_subject_means'])}")
    for subj, cell in results["eb2"]["d_cross_minus_same"]["per_subject"].items():
        print(f"    {subj:13s} D {_fmt_ci(cell['ci'])}   reps={cell['replicates']}")
    for name, block in (("rho_same", results["eb1"]["rho_same"]),
                        ("rho_gap", results["eb2"]["rho_gap"])):
        n = block["rate_undefined_replicates_excluded"]
        if n:
            print(f"  note: {n} replicate(s) had |S|=0 -> {name} undefined there "
                  "(counted, excluded from rate averages)")
    d = results["descriptives"]
    print("-" * 96)
    for key in ("loop_same", "loop_cross"):
        print(f"descriptives {key}: verdicts={d[key]['verdicts']} "
              f"mean_critic_rounds={d[key]['mean_critic_rounds']} "
              f"rejected_rounds={d[key]['rejected_rounds_total']}")
    flags = [f"{r['subject']}/rep{r['rep']}: {f}" for r in results["replicates"]
             for f in r.get("instrument_flags", [])]
    if flags:
        print(f"INSTRUMENT FLAGS ({len(flags)}): " + "; ".join(flags))
    s = results["spend"]
    print("-" * 96)
    print(f"spend: seeds=${s['seed_draws_usd']:.4f}  loop-same=${s['loop_same_usd']:.4f}  "
          f"loop-cross=${s['loop_cross_usd']:.4f}  runs-b-all=${s['runs_b_all_receipted_usd']:.4f} "
          f"(unattributed=${s['runs_b_unattributed_usd']:.4f})  "
          f"all-receipted=${s['all_receipted_total_usd']:.4f}")
    print("=" * 96)


def main(argv=None) -> int:
    results = run_analysis()
    print_report(results)
    out = REPO_ROOT / "experiments" / "results-b.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
