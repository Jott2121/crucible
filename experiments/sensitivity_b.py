#!/usr/bin/env python3
"""Post-hoc sensitivity analyses for Experiment B (paper Section 4.8) -- labeled
exploratory; the pre-registered primary analysis is analyze_b.py's. Recomputes,
from experiments/results-b.json: subject means and replicate-level values for the
cross-configuration estimands, leave-one-subject-out pooled means, the
truncation-replicate exclusion (packaging rep4), and two-stage bootstrap
intervals (resampling subjects, then replicates within subjects; same frozen RNG
seed and draw count as the protocol). Stdlib only.

Run: .venv/bin/python experiments/sensitivity_b.py
"""
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
r = json.loads((REPO / "experiments" / "results-b.json").read_text(encoding="utf-8"))
params = r["params"]
rows = [x for x in r["replicates"] if x.get("seed") == "ok"]
subs = params["subjects"]
KEYS = ("loop_same_delta", "loop_same_rho", "d_cross_minus_same", "rho_gap")


def vals(key, rows_):
    return {s: [x[key] for x in rows_ if x["subject"] == s and x.get(key) is not None]
            for s in subs}


def pooled_mean(key, rows_, exclude_subj=None):
    per = vals(key, rows_)
    means = [sum(v) / len(v) for s, v in per.items() if v and s != exclude_subj]
    return sum(means) / len(means) if means else None


def two_stage_ci(key, rows_):
    rng = random.Random(params["rng_seed"])
    draws = params["bootstrap_draws"]
    per = {s: v for s, v in vals(key, rows_).items() if v}
    names = sorted(per)
    out = []
    for _ in range(draws):
        picked = [names[rng.randrange(len(names))] for _ in names]
        ms = []
        for s in picked:
            v = per[s]
            ms.append(sum(v[rng.randrange(len(v))] for _ in v) / len(v))
        out.append(sum(ms) / len(ms))
    out.sort()
    return round(out[int(0.025 * draws)], 4), round(out[int(0.975 * draws) - 1], 4)


def main():
    no_rep4 = [x for x in rows if not (x["subject"] == "packaging" and x["rep"] == 4)]
    print("subject means:")
    for key in KEYS:
        per = vals(key, rows)
        print(f"  {key}: " + ", ".join(f"{s}={sum(v)/len(v):.4f}" for s, v in per.items() if v))
    print("replicate-level cross-configuration values:")
    for x in rows:
        print(f"  {x['subject']} rep{x['rep']}: D={x.get('d_cross_minus_same')} "
              f"rho_gap={x.get('rho_gap')}")
    print("pooled sensitivities:")
    for key in ("d_cross_minus_same", "rho_gap"):
        print(f"  {key}: full={pooled_mean(key, rows):.4f} "
              f"excl-packaging-rep4={pooled_mean(key, no_rep4):.4f}")
        for s in subs:
            print(f"    LOSO drop {s}: {pooled_mean(key, rows, exclude_subj=s):.4f}")
    print("two-stage bootstrap 95% intervals (subjects, then replicates within):")
    for key in KEYS:
        print(f"  {key}: full={two_stage_ci(key, rows)} "
              f"excl-packaging-rep4={two_stage_ci(key, no_rep4)}")


if __name__ == "__main__":
    main()
