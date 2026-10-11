"""Recompute published experiment figures from committed receipts.

Compares a fresh run of experiments/analyze.py and experiments/analyze_b.py to
experiments/results.json and experiments/results-b.json, then checks README.md,
experiments/RESULTS.md, and experiments/RESULTS-B.md still quote those headlines.
Does not rewrite the committed artifacts.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _walk_diff(fresh, committed, prefix: str, out: list[str], limit: int = 12) -> None:
    if len(out) >= limit:
        return
    if type(fresh) is not type(committed):
        out.append(f"{prefix}: type {type(fresh).__name__} != {type(committed).__name__}")
        return
    if isinstance(fresh, dict):
        for key in sorted(set(fresh) | set(committed)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in fresh:
                out.append(f"{path}: missing from recompute")
            elif key not in committed:
                out.append(f"{path}: not in committed artifact")
            else:
                _walk_diff(fresh[key], committed[key], path, out, limit)
        return
    if isinstance(fresh, list):
        if len(fresh) != len(committed):
            out.append(f"{prefix}: len {len(fresh)} != {len(committed)}")
            return
        for i, (left, right) in enumerate(zip(fresh, committed)):
            _walk_diff(left, right, f"{prefix}[{i}]", out, limit)
        return
    if fresh != committed:
        out.append(f"{prefix}: {fresh!r} != {committed!r}")


def _require(label: str, text: str, needle: str, errors: list[str]) -> None:
    if needle not in text:
        errors.append(f"{label} does not contain {needle!r}")


def _fmt_ci(ci: dict) -> tuple[str, str]:
    """Three-decimal mean and interval, checked separately.

    README prose splits them (`rate 0.783, 95% bootstrap interval [0.592, 0.935]`).
    RESULTS-B.md prints them together (`0.783 [0.592, 0.935]`). Either form contains both pieces.
    """
    return f"{ci['mean']:.3f}", f"[{ci['lo95']:.3f}, {ci['hi95']:.3f}]"


def _fmt_p(p: float) -> str:
    exp = math.floor(math.log10(p))
    mant = p / 10**exp
    text = f"{mant:.1f}"
    if text == "10.0":
        text = "1.0"
        exp += 1
    return f"{text}×10{str(exp).translate(_SUP)}"


def main() -> int:
    analyze = _load("crucible_analyze", ROOT / "experiments" / "analyze.py")
    analyze_b = _load("crucible_analyze_b", ROOT / "experiments" / "analyze_b.py")
    errors: list[str] = []

    fresh = analyze.run_analysis()
    committed = json.loads((ROOT / "experiments" / "results.json").read_text(encoding="utf-8"))
    diff: list[str] = []
    _walk_diff(fresh, committed, "results.json", diff)
    if diff:
        errors.append("experiments/results.json drifted from experiments/analyze.py:")
        errors.extend(f"  {line}" for line in diff)

    fresh_b = analyze_b.run_analysis()
    committed_b = json.loads((ROOT / "experiments" / "results-b.json").read_text(encoding="utf-8"))
    diff_b: list[str] = []
    _walk_diff(fresh_b, committed_b, "results-b.json", diff_b)
    if diff_b:
        errors.append("experiments/results-b.json drifted from experiments/analyze_b.py:")
        errors.extend(f"  {line}" for line in diff_b)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    results_md = (ROOT / "experiments" / "RESULTS.md").read_text(encoding="utf-8")
    results_b_md = (ROOT / "experiments" / "RESULTS-B.md").read_text(encoding="utf-8")

    if not diff:
        h1 = fresh["h1"]["pooled_with_attrition"]
        p_text = _fmt_p(h1["p"])
        discordant = f"{h1['b']} discordant"
        for label, text in (("README.md", readme), ("experiments/RESULTS.md", results_md)):
            _require(label, text, discordant, errors)
            _require(label, text, p_text, errors)
        _require("experiments/RESULTS.md", results_md, f"c = {h1['c']}", errors)

    if not diff_b:
        for label, text in (("README.md", readme), ("experiments/RESULTS-B.md", results_b_md)):
            for ci in (
                fresh_b["eb1"]["rho_same"]["pooled_unweighted_subject_means"],
                fresh_b["eb2"]["rho_gap"]["pooled_unweighted_subject_means"],
            ):
                mean, interval = _fmt_ci(ci)
                _require(label, text, mean, errors)
                _require(label, text, interval, errors)

    if errors:
        print("receipt check failed:", file=sys.stderr)
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    h1 = fresh["h1"]["pooled_with_attrition"]
    rho_mean, rho_iv = _fmt_ci(fresh_b["eb1"]["rho_same"]["pooled_unweighted_subject_means"])
    gap_mean, gap_iv = _fmt_ci(fresh_b["eb2"]["rho_gap"]["pooled_unweighted_subject_means"])
    print("receipts ok")
    print(f"  H1 pooled discordant b={h1['b']} c={h1['c']} p={_fmt_p(h1['p'])}")
    print(f"  E-B1 pooled rho_same {rho_mean} {rho_iv}")
    print(f"  E-B2 pooled rho_gap {gap_mean} {gap_iv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
