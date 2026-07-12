"""Turn receipts into the paper's numbers. Stdlib only; every figure recomputable
by a reader from the receipt files alone.
"""
from __future__ import annotations

from math import comb


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar on discordant pair counts (b: A-only, c: B-only)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def _killed(run: dict) -> set[str]:
    return {m for r in run["rounds"] for m in r.get("kills", [])}


def _baseline(run: dict) -> set[str]:
    """Pristine-baseline survivors: what survived BEFORE any generated test ran
    (round 0's survivors_before, measured on the untouched clone)."""
    for r in run["rounds"]:
        if r["round"] == 0:
            return set(r.get("survivors_before", []))
    return set()


def paired_kills(run_a: dict, run_b: dict) -> tuple[int, int, int, int]:
    union = _baseline(run_a) | _baseline(run_b)
    ka, kb = _killed(run_a), _killed(run_b)
    both = len(union & ka & kb)
    a_only = len((union & ka) - kb)
    b_only = len((union & kb) - ka)
    neither = len(union - ka - kb)
    return both, a_only, b_only, neither


def summarize(run: dict) -> dict:
    killed = len(_killed(run))
    cost = run["result"]["total_cost_usd"] if run["result"] else 0.0
    return {
        "arm": run["meta"].get("arm"),
        "verdict": run["result"]["verdict"] if run["result"] else "incomplete",
        "baseline_survivors": len(_baseline(run)),
        "killed": killed,
        "cost_usd": cost,
        "cost_per_kill": (cost / killed) if killed else None,
        "billing": (lambda t, c: t if t == c else f"mixed:{t}+{c}")(
            run["meta"].get("tester_billing", "api"),
            run["meta"].get("critic_billing", "api")),
    }
