"""Unit tests for experiments/analyze.py against crafted receipt dirs (never real
experiments/runs/ data -- this suite must pass with zero dependency on the real grid)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ANALYZE_PATH = Path(__file__).resolve().parents[1] / "experiments" / "analyze.py"
_spec = importlib.util.spec_from_file_location("experiments_analyze", _ANALYZE_PATH)
analyze = importlib.util.module_from_spec(_spec)
sys.modules["experiments_analyze"] = analyze
_spec.loader.exec_module(analyze)


def write_run(runs_root, subject, run_name, rounds, result, meta_extra=None):
    """Write a receipt dir shaped exactly like crucible.receipts.ReceiptWriter output."""
    run_dir = runs_root / subject / run_name
    run_dir.mkdir(parents=True)
    meta = {"subject": f"/fake/{subject}", "module": "pkg/mod.py", "arm": run_name.split("-")[0]}
    if meta_extra:
        meta.update(meta_extra)
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if rounds is not None:
        lines = "\n".join(json.dumps(r) for r in rounds)
        (run_dir / "receipt.jsonl").write_text(lines + "\n" if lines else "", encoding="utf-8")
    if result is not None:
        (run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return run_dir


def _round(round_no, role, kills, survivors_before=None, dropped=None, status="ok", cost=0.1):
    r = {"round": round_no, "role": role, "kills": kills, "status": status, "cost_usd": cost}
    if survivors_before is not None:
        r["survivors_before"] = survivors_before
        r["survivors_after"] = [m for m in survivors_before if m not in kills]
    if dropped is not None:
        r["dropped_tests"] = dropped
    return r


def make_subject(runs_root, subject, baseline, oneshot_kills, loop_same_r0_kills,
                  loop_same_r1_kills, loop_cross_r0_kills, loop_cross_r1_kills,
                  oneshot_dropped=None, cost=0.1, loop_cross_verdict="clean",
                  baseline_all_mutants=None, pre_killed=0):
    """baseline = full list of pristine survivor mutant ids, shared across all 3 arms (same
    subject-module, same pristine measure). Each arm's tester/critic rounds are independent
    (real crucible cells never share a round-0 draw across arms), so callers pick each arm's
    kill sets directly to dial in an exact discordant-pair count."""
    baseline_all = baseline_all_mutants or len(baseline)
    common = dict(baseline_all_mutants=baseline_all,
                  baseline_counts={"killed": pre_killed, "survived": len(baseline)})

    write_run(runs_root, subject, f"oneshot-{subject}", [
        _round(0, "tester", oneshot_kills, survivors_before=baseline, dropped=oneshot_dropped or []),
    ], {"verdict": "oneshot", "total_cost_usd": cost, "baseline_survivors": baseline, **common})

    write_run(runs_root, subject, f"loop_same-{subject}", [
        _round(0, "tester", loop_same_r0_kills, survivors_before=baseline, dropped=[]),
        _round(1, "critic", loop_same_r1_kills, dropped=[]),
    ], {"verdict": "dry" if loop_same_r1_kills else "clean", "total_cost_usd": cost,
        "baseline_survivors": baseline, **common})

    if loop_cross_verdict == "rejected":
        write_run(runs_root, subject, f"loop_cross-{subject}", [
            _round(0, "tester", [], survivors_before=baseline, dropped=[], status="rejected"),
        ], {"verdict": "rejected", "total_cost_usd": cost, "baseline_survivors": baseline, **common})
    else:
        write_run(runs_root, subject, f"loop_cross-{subject}", [
            _round(0, "tester", loop_cross_r0_kills, survivors_before=baseline, dropped=[]),
            _round(1, "critic", loop_cross_r1_kills, dropped=[]),
        ], {"verdict": "dry" if loop_cross_r1_kills else "clean", "total_cost_usd": cost,
            "baseline_survivors": baseline, **common})

    return {
        "oneshot": f"oneshot-{subject}",
        "loop_same": f"loop_same-{subject}",
        "loop_cross": f"loop_cross-{subject}",
        "justification": "synthetic fixture",
    }


@pytest.fixture
def counted_fixture(tmp_path):
    runs_root = tmp_path / "runs"
    counted = {}
    # subject "alpha": loop-same beats oneshot (b=2,c=0); loop-cross beats loop-same (b=1,c=0)
    counted["alpha"] = make_subject(
        runs_root, "alpha", baseline=["m1", "m2", "m3", "m4", "m5"],
        oneshot_kills=["m1"],
        loop_same_r0_kills=["m1"], loop_same_r1_kills=["m2", "m3"],
        loop_cross_r0_kills=["m1"], loop_cross_r1_kills=["m2", "m3", "m4"],
        cost=1.0,
    )
    # subject "beta": ties on H1 (b=1,c=1); loop-cross cell REJECTED -> missing H2 cell
    counted["beta"] = make_subject(
        runs_root, "beta", baseline=["n1", "n2", "n3"],
        oneshot_kills=["n1", "n3"],
        loop_same_r0_kills=["n1"], loop_same_r1_kills=["n2"],
        loop_cross_r0_kills=[], loop_cross_r1_kills=[],
        loop_cross_verdict="rejected", cost=0.5,
    )
    # subject "attrition-risk-ml": degenerate 0-kill oneshot baseline (excluded from
    # pooled-without-attrition only)
    counted["attrition-risk-ml"] = make_subject(
        runs_root, "attrition-risk-ml", baseline=["z1", "z2"],
        oneshot_kills=[],
        loop_same_r0_kills=[], loop_same_r1_kills=["z1"],
        loop_cross_r0_kills=[], loop_cross_r1_kills=["z2"],
        cost=0.2,
    )
    counted_path = tmp_path / "counted.json"
    counted_path.write_text(json.dumps({"subjects": counted}), encoding="utf-8")
    return counted_path, runs_root


def test_load_counted_runs_reads_all_three_arms(counted_fixture):
    counted_path, runs_root = counted_fixture
    counted = analyze.load_counted(counted_path)
    runs = analyze.load_counted_runs(counted, runs_root)
    assert set(runs) == {"alpha", "beta", "attrition-risk-ml"}
    assert set(runs["alpha"]) == {"oneshot", "loop_same", "loop_cross"}


def test_load_counted_runs_missing_dir_raises(tmp_path):
    counted = {"ghost": {"oneshot": "does-not-exist", "loop_same": "x", "loop_cross": "y"}}
    with pytest.raises(FileNotFoundError):
        analyze.load_counted_runs(counted, tmp_path / "runs")


def test_per_subject_h1_direction_and_counts(counted_fixture):
    counted_path, runs_root = counted_fixture
    runs = analyze.load_counted_runs(analyze.load_counted(counted_path), runs_root)
    h1 = analyze.per_subject_h1(runs)
    assert h1["alpha"]["b_loop_same_only"] == 2
    assert h1["alpha"]["c_oneshot_only"] == 0
    assert h1["alpha"]["favors_loop_same"] is True
    assert h1["beta"]["b_loop_same_only"] == 1
    assert h1["beta"]["c_oneshot_only"] == 1
    assert h1["beta"]["favors_loop_same"] is False  # tie does not favor loop-same


def test_per_subject_h2_excludes_rejected_cell(counted_fixture):
    counted_path, runs_root = counted_fixture
    runs = analyze.load_counted_runs(analyze.load_counted(counted_path), runs_root)
    h2 = analyze.per_subject_h2(runs)
    assert "excluded" in h2["beta"]
    assert "rejected" in h2["beta"]["excluded"]
    assert "excluded" not in h2["alpha"]
    assert h2["alpha"]["b_loop_cross_only"] == 1
    assert h2["alpha"]["favors_loop_cross"] is True


def test_pooled_view_excludes_attrition_when_requested(counted_fixture):
    counted_path, runs_root = counted_fixture
    runs = analyze.load_counted_runs(analyze.load_counted(counted_path), runs_root)
    h1 = analyze.per_subject_h1(runs)
    with_attr = analyze.pooled_view(h1, "b_loop_same_only", "c_oneshot_only", include_attrition=True)
    without_attr = analyze.pooled_view(h1, "b_loop_same_only", "c_oneshot_only", include_attrition=False)
    # alpha: b=2,c=0 ; beta: b=1,c=1 ; attrition: b=1,c=0
    assert with_attr["b"] == 4 and with_attr["c"] == 1
    assert without_attr["b"] == 3 and without_attr["c"] == 1
    assert "attrition-risk-ml" not in without_attr["subjects"]
    assert "attrition-risk-ml" in with_attr["subjects"]


def test_pooled_view_skips_excluded_h2_cells(counted_fixture):
    counted_path, runs_root = counted_fixture
    runs = analyze.load_counted_runs(analyze.load_counted(counted_path), runs_root)
    h2 = analyze.per_subject_h2(runs)
    pooled = analyze.pooled_view(h2, "b_loop_cross_only", "c_loop_same_only", include_attrition=True)
    assert "beta" not in pooled["subjects"]
    assert set(pooled["subjects"]) == {"alpha", "attrition-risk-ml"}


def test_mcnemar_known_value_matches_report_module(counted_fixture):
    counted_path, runs_root = counted_fixture
    runs = analyze.load_counted_runs(analyze.load_counted(counted_path), runs_root)
    h1 = analyze.per_subject_h1(runs)
    # alpha: b=2, c=0 -> p = 2 * (0.5**2) = 0.5
    assert h1["alpha"]["p"] == pytest.approx(0.5)


def test_cell_is_valid_true_for_ok_verdict_false_for_rejected_or_missing():
    ok_run = {"result": {"verdict": "clean"}}
    rejected_run = {"result": {"verdict": "rejected"}}
    aborted_run = {"result": {"verdict": "aborted"}}
    missing_run = {"result": None}
    assert analyze.cell_is_valid(ok_run) is True
    assert analyze.cell_is_valid(rejected_run) is False
    assert analyze.cell_is_valid(aborted_run) is False
    assert analyze.cell_is_valid(missing_run) is False


def test_dropped_tests_flattens_across_rounds():
    run = {"rounds": [
        {"round": 0, "dropped_tests": ["test_a"]},
        {"round": 1, "dropped_tests": []},
        {"round": 2, "dropped_tests": ["test_b", "test_c"]},
        {"round": 3},  # no dropped_tests key at all -- must not crash
    ]}
    assert analyze.dropped_tests(run) == ["test_a", "test_b", "test_c"]


def test_arm_table_missing_cell_never_renders_receipted_kills(counted_fixture):
    """A Sec.6-missing cell (rejected/aborted verdict, or no result.json) must
    render killed=None and a MISSING verdict in the cell table -- its receipted
    per-round kill data is preserved evidence, never a counted measurement.
    Billed spend still appears, summed from the receipt rows."""
    counted_path, runs_root = counted_fixture
    runs = analyze.load_counted_runs(analyze.load_counted(counted_path), runs_root)
    rows = analyze.arm_table(runs)
    beta_loop_cross = next(r for r in rows if r["subject"] == "beta" and r["arm"] == "loop_cross")
    assert beta_loop_cross["killed"] is None
    assert beta_loop_cross["cost_per_kill"] is None
    assert beta_loop_cross["verdict"] == "MISSING (rejected)"
    assert beta_loop_cross["cost_usd"] == pytest.approx(
        sum(r.get("cost_usd", 0.0) for r in runs["beta"]["loop_cross"]["rounds"]))


def test_arm_table_cost_per_kill_none_safe_on_valid_zero_kill_cell():
    """The original divide-by-zero guard, on a VALID cell: verdict ok, zero
    kills -> killed=0 and cost_per_kill None (never a ZeroDivisionError)."""
    run = {
        "meta": {"arm": "oneshot"},
        "rounds": [{"round": 0, "role": "tester", "status": "ok",
                    "survivors_before": ["m1", "m2"], "survivors_after": ["m1", "m2"],
                    "kills": [], "cost_usd": 0.05}],
        "result": {"verdict": "oneshot", "total_cost_usd": 0.05,
                   "baseline_survivors": ["m1", "m2"]},
    }
    rows = analyze.arm_table({"solo": {"oneshot": run,
                                        "loop_same": run, "loop_cross": run}})
    assert all(r["killed"] == 0 and r["cost_per_kill"] is None for r in rows)


def test_arm_table_mutation_score_full_denominator(counted_fixture):
    counted_path, runs_root = counted_fixture
    runs = analyze.load_counted_runs(analyze.load_counted(counted_path), runs_root)
    rows = analyze.arm_table(runs)
    alpha_oneshot = next(r for r in rows if r["subject"] == "alpha" and r["arm"] == "oneshot")
    # baseline_all_mutants defaults to len(baseline)=5, pre_killed=0, killed=1 -> 20.0%
    assert alpha_oneshot["mutation_score_full_denom_pct"] == pytest.approx(20.0)
    assert alpha_oneshot["kill_rate_pct_of_survivors"] == pytest.approx(20.0)


def test_total_spend_counted_vs_all_receipted(counted_fixture):
    counted_path, runs_root = counted_fixture
    counted = analyze.load_counted(counted_path)
    # add a shakeout dir NOT referenced by counted.json
    write_run(runs_root, "alpha", "shakeout-attempt1", [
        _round(0, "tester", [], survivors_before=["m1"], status="rejected"),
    ], {"verdict": "rejected", "total_cost_usd": 0.37})
    spend = analyze.total_spend(runs_root, counted)
    assert spend["counted_n_receipts"] == 9  # 3 subjects x 3 arms
    assert spend["all_n_receipts"] == 10
    assert spend["shakeout_total_usd"] == pytest.approx(0.37)
    assert spend["all_receipted_total_usd"] == pytest.approx(spend["counted_total_usd"] + 0.37)


def test_run_analysis_end_to_end_shape(counted_fixture):
    counted_path, runs_root = counted_fixture
    results = analyze.run_analysis(counted_path, runs_root)
    assert set(results) == {"counted", "h1", "h2", "arms", "spend"}
    assert set(results["h1"]) == {"per_subject", "pooled_with_attrition", "pooled_without_attrition"}
    assert len(results["arms"]) == 9  # 3 subjects x 3 arms
    # JSON-serializable end to end (results.json must be machine-readable)
    json.dumps(results)
