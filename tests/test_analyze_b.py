import importlib.util
import json
import random
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "analyze_b", Path(__file__).resolve().parents[1] / "experiments" / "analyze_b.py")
analyze_b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze_b)

PARAMS = {"k": 2, "subjects": ["subj"], "bootstrap_draws": 200, "rng_seed": 20260713}
SEED_SHA = "a" * 64


def _write_seed(root, subject, rep, baseline=("m1", "m2", "m3"), post=("m3",),
                sha=SEED_SHA, draw_cost=0.1):
    rep_dir = root / "seeds" / subject / f"rep{rep}"
    (rep_dir / "draws" / "draw-1").mkdir(parents=True)
    (rep_dir / "draws" / "draw-1" / "result.json").write_text(
        json.dumps({"verdict": "oneshot", "total_cost_usd": draw_cost}))
    (rep_dir / "draws" / "draw-1" / "receipt.jsonl").write_text(
        json.dumps({"round": 0, "role": "tester", "cost_usd": draw_cost}) + "\n")
    (rep_dir / "seed.json").write_text(json.dumps({
        "baseline_survivors": list(baseline), "post_survivors": list(post),
        "test_sha256": sha}))
    return rep_dir


def _write_cell(root, subject, arm, rep, verdict="dry", kills_by_round=((("m1", "m2"),), ),
                cost=0.05, sha=SEED_SHA, stamp="20260713T000000Z", crashed=False):
    d = root / "runs-b" / subject / f"{arm}-rep{rep}-{stamp}"
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"seed": {"test_sha256": sha}}))
    lines = []
    for i, kills in enumerate(kills_by_round):
        role = "tester" if i == 0 else "critic"
        lines.append(json.dumps({"round": i, "role": role, "kills": list(kills[0]) if kills else [],
                                 "status": "ok", "cost_usd": cost / max(len(kills_by_round), 1)}))
    (d / "receipt.jsonl").write_text("\n".join(lines) + "\n")
    if not crashed:
        (d / "result.json").write_text(json.dumps({"verdict": verdict, "total_cost_usd": cost}))
    return d


def test_replicate_row_computes_deltas_and_rates(tmp_path):
    _write_seed(tmp_path, "subj", 1)  # baseline 3, post 1 -> k0 = 2
    # loop-same: round0 kills m1,m2 (k0), critic kills m3 -> total 3, delta 1
    _write_cell(tmp_path, "subj", "loop-same", 1, verdict="clean",
                kills_by_round=((("m1", "m2"),), (("m3",),)))
    # loop-cross: critic kills nothing -> delta 0
    _write_cell(tmp_path, "subj", "loop-cross", 1, verdict="dry",
                kills_by_round=((("m1", "m2"),), ((),)))
    _write_seed(tmp_path, "subj", 2)
    _write_cell(tmp_path, "subj", "loop-same", 2, verdict="dry",
                kills_by_round=((("m1", "m2"),), ((),)))
    _write_cell(tmp_path, "subj", "loop-cross", 2, verdict="dry",
                kills_by_round=((("m1", "m2"),), ((),)))
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    r1 = rows[0]
    assert (r1["n_base"], r1["s"], r1["k0"]) == (3, 1, 2)
    assert r1["loop_same_delta"] == 1
    assert r1["loop_same_rho"] == 1.0
    assert r1["loop_cross_delta"] == 0
    assert r1["d_cross_minus_same"] == -1
    assert r1["loop_same_cost_per_delta"] == 0.05
    assert r1["loop_cross_cost_per_delta"] is None  # delta 0: ratio undefined


def test_find_cell_skips_retired_seed_and_sums_crashed_spend(tmp_path):
    _write_seed(tmp_path, "subj", 1)
    _write_cell(tmp_path, "subj", "loop-same", 1, verdict="dry", sha="0" * 64,
                stamp="20260713T000000Z")                      # retired seed's cell
    _write_cell(tmp_path, "subj", "loop-same", 1, crashed=True, cost=0.03,
                stamp="20260713T010000Z")                      # crashed under current seed
    cell = analyze_b.find_cell(tmp_path / "runs-b", "subj", "loop-same", 1, SEED_SHA)
    assert cell["status"] == "missing"
    assert cell["attempt_statuses"] == ["crashed"]             # retired dir not even counted
    assert cell["spent_usd"] == 0.03                           # billed rounds stay visible


def test_zero_survivor_seed_counts_but_has_no_rate(tmp_path):
    _write_seed(tmp_path, "subj", 1, baseline=("m1",), post=())   # |S|=0
    _write_cell(tmp_path, "subj", "loop-same", 1, verdict="clean",
                kills_by_round=((("m1",),),))
    _write_seed(tmp_path, "subj", 2)
    _write_cell(tmp_path, "subj", "loop-same", 2, verdict="clean",
                kills_by_round=((("m1", "m2"),), (("m3",),)))
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    assert rows[0]["loop_same_delta"] == 0
    assert rows[0]["loop_same_rho"] is None
    rng = random.Random(PARAMS["rng_seed"])
    delta = analyze_b.estimand(rows, "loop_same_delta", ("loop-same",), PARAMS, rng)
    rho = analyze_b.estimand(rows, "loop_same_rho", ("loop-same",), PARAMS, rng)
    assert delta["per_subject"]["subj"]["ci"]["n"] == 2        # counts include the |S|=0 rep
    assert rho["per_subject"]["subj"]["ci"]["n"] == 1          # rates exclude it
    assert rho["rate_undefined_replicates_excluded"] == 1


def test_estimand_composition_is_per_estimand(tmp_path):
    _write_seed(tmp_path, "subj", 1)
    _write_cell(tmp_path, "subj", "loop-same", 1, verdict="dry",
                kills_by_round=((("m1", "m2"),), (("m3",),)))
    # loop-cross rep1 crashed -> E-B1 keeps the replicate, E-B2 loses it
    _write_cell(tmp_path, "subj", "loop-cross", 1, crashed=True)
    _write_seed(tmp_path, "subj", 2)
    _write_cell(tmp_path, "subj", "loop-same", 2, verdict="dry",
                kills_by_round=((("m1", "m2"),), ((),)))
    _write_cell(tmp_path, "subj", "loop-cross", 2, verdict="dry",
                kills_by_round=((("m1", "m2"),), ((),)))
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    rng = random.Random(PARAMS["rng_seed"])
    eb1 = analyze_b.estimand(rows, "loop_same_delta", ("loop-same",), PARAMS, rng)
    eb2 = analyze_b.estimand(rows, "d_cross_minus_same", ("loop-same", "loop-cross"),
                             PARAMS, rng)
    assert eb1["replicate_composition"]["subj"] == [1, 2]
    assert eb2["replicate_composition"]["subj"] == [2]


def test_bootstrap_is_deterministic_under_frozen_seed():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    a = analyze_b.bootstrap_ci(values, random.Random(20260713), 500)
    b = analyze_b.bootstrap_ci(values, random.Random(20260713), 500)
    assert a == b
    assert a["mean"] == 3.0
    assert a["lo95"] <= 3.0 <= a["hi95"]


def test_bootstrap_empty_returns_none():
    assert analyze_b.bootstrap_ci([], random.Random(1), 100) is None


def test_pooled_is_unweighted_mean_of_subject_means(tmp_path):
    params = dict(PARAMS, subjects=["big", "small"], k=1)
    # big subject: delta 10; small subject: delta 0 -- pooled mean must be 5.0
    _write_seed(tmp_path, "big", 1, baseline=[f"m{i}" for i in range(20)],
                post=[f"m{i}" for i in range(10, 20)])
    _write_cell(tmp_path, "big", "loop-same", 1, verdict="clean",
                kills_by_round=(((tuple(f"m{i}" for i in range(10))),),
                                ((tuple(f"m{i}" for i in range(10, 20))),)))
    _write_seed(tmp_path, "small", 1)
    _write_cell(tmp_path, "small", "loop-same", 1, verdict="dry",
                kills_by_round=((("m1", "m2"),), ((),)))
    rows = analyze_b.replicate_rows(params, tmp_path / "seeds", tmp_path / "runs-b")
    rng = random.Random(params["rng_seed"])
    eb1 = analyze_b.estimand(rows, "loop_same_delta", ("loop-same",), params, rng)
    assert eb1["pooled_unweighted_subject_means"]["mean"] == 5.0
    assert eb1["pooled_unweighted_subject_means"]["n_subjects"] == 2


def test_spend_summary_separates_seed_and_continuation_spend(tmp_path):
    _write_seed(tmp_path, "subj", 1, draw_cost=0.25)
    _write_cell(tmp_path, "subj", "loop-same", 1, cost=0.06)
    _write_cell(tmp_path, "subj", "loop-cross", 1, cost=0.02)
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    spend = analyze_b.spend_summary(rows, tmp_path / "seeds", tmp_path / "runs-b")
    assert spend["seed_draws_usd"] == 0.25
    assert spend["loop_same_usd"] == 0.06
    assert spend["loop_cross_usd"] == 0.02
    assert spend["all_receipted_total_usd"] == 0.33
    assert spend["runs_b_unattributed_usd"] == 0.0


def test_missing_seed_renders_as_missing_never_zero(tmp_path):
    _write_seed(tmp_path, "subj", 2)  # rep1 has no seed at all
    _write_cell(tmp_path, "subj", "loop-same", 2, verdict="dry",
                kills_by_round=((("m1", "m2"),), ((),)))
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    assert rows[0]["seed"] == "missing"
    assert "loop_same_delta" not in rows[0]
    rng = random.Random(PARAMS["rng_seed"])
    eb1 = analyze_b.estimand(rows, "loop_same_delta", ("loop-same",), PARAMS, rng)
    assert eb1["replicate_composition"]["subj"] == [2]


def test_params_load_from_the_frozen_protocol():
    params = analyze_b.load_analysis_params()
    assert params["rng_seed"] == 20260713
    assert params["bootstrap_draws"] == 10000
    assert params["k"] == 5
    assert params["subjects"] == ["graph-guard", "idna", "packaging", "rag-guard"]


def test_eb2_rate_analogue_is_the_within_replicate_paired_gap(tmp_path):
    # review finding B1: Sec.5 pre-registers rho_gap = rho_cross - rho_same
    # paired WITHIN replicate -- not plain rho_cross wearing its name
    _write_seed(tmp_path, "subj", 1)  # baseline 3, post 1
    _write_cell(tmp_path, "subj", "loop-same", 1, verdict="clean",
                kills_by_round=((("m1", "m2"),), (("m3",),)))     # rho_same = 1.0
    _write_cell(tmp_path, "subj", "loop-cross", 1, verdict="dry",
                kills_by_round=((("m1", "m2"),), ((),)))          # rho_cross = 0.0
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    assert rows[0]["rho_gap"] == -1.0
    rng = random.Random(PARAMS["rng_seed"])
    gap = analyze_b.estimand(rows, "rho_gap", ("loop-same", "loop-cross"), PARAMS, rng)
    assert gap["per_subject"]["subj"]["ci"]["mean"] == -1.0


def test_rho_gap_undefined_at_zero_survivors(tmp_path):
    _write_seed(tmp_path, "subj", 1, baseline=("m1",), post=())
    _write_cell(tmp_path, "subj", "loop-same", 1, verdict="clean",
                kills_by_round=((("m1",),),))
    _write_cell(tmp_path, "subj", "loop-cross", 1, verdict="clean",
                kills_by_round=((("m1",),),))
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    assert "rho_gap" not in rows[0]
    assert rows[0]["d_cross_minus_same"] == 0    # the count gap stays defined


def test_two_valid_receipts_for_one_cell_fail_loud(tmp_path):
    # review finding S2: impossible via the runner's Sec.8 gate, so its presence
    # is a protocol violation -- never silently pick one
    import pytest
    _write_seed(tmp_path, "subj", 1)
    _write_cell(tmp_path, "subj", "loop-same", 1, stamp="20260713T000000Z")
    _write_cell(tmp_path, "subj", "loop-same", 1, stamp="20260713T010000Z")
    with pytest.raises(ValueError, match="TWO validly scored"):
        analyze_b.find_cell(tmp_path / "runs-b", "subj", "loop-same", 1, SEED_SHA)


def test_receipt_disagreeing_with_its_seed_fails_loud(tmp_path):
    import pytest
    _write_seed(tmp_path, "subj", 1)  # k0 = 2
    _write_cell(tmp_path, "subj", "loop-same", 1, verdict="dry",
                kills_by_round=((("m1",),), ((),)))  # round-0 kills 1 != k0 2
    with pytest.raises(ValueError, match="k0"):
        analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")


def test_negative_delta_is_flagged_never_averaged(tmp_path, capsys):
    # review finding S4 + SF1: drive the guard for real. A receipt whose rounds
    # lack a round==0 record skips the k0 integrity check (round0_kills None)
    # and its killed_total 0 < k0 2 produces the negative delta the Sec.4 gate
    # makes unreachable from the real instrument -- the analyzer must flag it,
    # exclude it, and say so in the printed report.
    _write_seed(tmp_path, "subj", 1)  # k0 = 2
    d = tmp_path / "runs-b" / "subj" / "loop-same-rep1-20260713T000000Z"
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"seed": {"test_sha256": SEED_SHA}}))
    (d / "receipt.jsonl").write_text(
        json.dumps({"round": 1, "role": "critic", "kills": [], "status": "ok",
                    "cost_usd": 0.01}) + "\n")
    (d / "result.json").write_text(json.dumps({"verdict": "dry", "total_cost_usd": 0.01}))
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    assert rows[0]["loop_same"]["status"] == "invalid-negative-delta"
    assert "loop_same_delta" not in rows[0]
    assert rows[0]["instrument_flags"] == ["loop-same: delta -2 < 0 -- instrument failure (Sec.4)"]
    rng = random.Random(PARAMS["rng_seed"])
    eb1 = analyze_b.estimand(rows, "loop_same_delta", ("loop-same",), PARAMS, rng)
    assert eb1["replicate_composition"]["subj"] == []      # excluded, never averaged
    results = {"replicates": rows, "params": PARAMS,
               "eb1": {"delta_same": eb1, "rho_same": eb1},
               "eb2": {"d_cross_minus_same": eb1, "rho_gap": eb1, "rho_cross": eb1},
               "descriptives": analyze_b.descriptives(rows),
               "spend": analyze_b.spend_summary(rows, tmp_path / "seeds", tmp_path / "runs-b")}
    analyze_b.print_report(results)
    assert "INSTRUMENT FLAGS (1)" in capsys.readouterr().out


def test_seed_spend_counts_crashed_draws(tmp_path):
    # reviewer SF2: a draw that billed rounds but crashed before result.json
    # must still appear in seed spend (Experiment 1's disclosed $0.21 class)
    _write_seed(tmp_path, "subj", 1, draw_cost=0.10)
    crashed = tmp_path / "seeds" / "subj" / "rep2" / "draws" / "draw-1"
    crashed.mkdir(parents=True)
    (crashed / "receipt.jsonl").write_text(
        json.dumps({"round": 0, "role": "tester", "cost_usd": 0.33}) + "\n")
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    spend = analyze_b.spend_summary(rows, tmp_path / "seeds", tmp_path / "runs-b")
    assert spend["seed_draws_usd"] == 0.43


def test_descriptives_aggregate_per_arm(tmp_path):
    _write_seed(tmp_path, "subj", 1)
    _write_cell(tmp_path, "subj", "loop-same", 1, verdict="dry",
                kills_by_round=((("m1", "m2"),), (("m3",),), ((),)))  # 2 critic rounds
    _write_cell(tmp_path, "subj", "loop-cross", 1, verdict="clean",
                kills_by_round=((("m1", "m2"),), (("m3",),)))
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    d = analyze_b.descriptives(rows)
    assert d["loop_same"]["verdicts"] == {"dry": 1}
    assert d["loop_same"]["mean_critic_rounds"] == 2.0
    assert d["loop_cross"]["verdicts"] == {"clean": 1}


def test_spend_all_receipts_walk_catches_unattributed_dollars(tmp_path):
    # review finding S1: retired-seed receipts and seedless reps' receipts must
    # still appear in the all-receipted total
    _write_seed(tmp_path, "subj", 1, draw_cost=0.10)
    _write_cell(tmp_path, "subj", "loop-same", 1, cost=0.06)
    # a retired seed's receipt: attribution skips it, the walk must not
    _write_cell(tmp_path, "subj", "loop-same", 1, sha="0" * 64, cost=0.05,
                stamp="20260713T020000Z")
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    spend = analyze_b.spend_summary(rows, tmp_path / "seeds", tmp_path / "runs-b")
    assert spend["loop_same_usd"] == 0.06
    assert spend["runs_b_all_receipted_usd"] == 0.11
    assert spend["runs_b_unattributed_usd"] == 0.05
    assert spend["all_receipted_total_usd"] == 0.21


def test_pooled_states_its_subject_composition(tmp_path):
    _write_seed(tmp_path, "subj", 1)
    _write_cell(tmp_path, "subj", "loop-same", 1, verdict="dry",
                kills_by_round=((("m1", "m2"),), ((),)))
    rows = analyze_b.replicate_rows(PARAMS, tmp_path / "seeds", tmp_path / "runs-b")
    rng = random.Random(PARAMS["rng_seed"])
    eb1 = analyze_b.estimand(rows, "loop_same_delta", ("loop-same",), PARAMS, rng)
    assert eb1["pooled_unweighted_subject_means"]["subjects"] == ["subj"]


def test_run_analysis_is_reproducible_end_to_end(tmp_path, capsys):
    proto = tmp_path / "protocol-b.json"
    proto.write_text(json.dumps({
        "replicates": {"k": 1}, "subjects": {"subj": {"module": "m.py"}},
        "analysis": {"bootstrap_draws": 300, "rng_seed": 20260713}}))
    _write_seed(tmp_path, "subj", 1)
    _write_cell(tmp_path, "subj", "loop-same", 1, verdict="dry",
                kills_by_round=((("m1", "m2"),), (("m3",),)))
    _write_cell(tmp_path, "subj", "loop-cross", 1, verdict="dry",
                kills_by_round=((("m1", "m2"),), ((),)))
    a = analyze_b.run_analysis(proto, tmp_path / "seeds", tmp_path / "runs-b")
    b = analyze_b.run_analysis(proto, tmp_path / "seeds", tmp_path / "runs-b")
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    analyze_b.print_report(a)   # smoke: the paper quotes these tables
    out = capsys.readouterr().out
    assert "E-B1" in out and "rho-gap" in out and "all-receipted" in out
