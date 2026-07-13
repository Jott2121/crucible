import json
import subprocess
from pathlib import Path

import pytest

from crucible.experiment_b import (
    ProtocolBError,
    _load_seed,
    _next_rep_needing_seed,
    assert_dir_committed,
    generate_seed,
    load_protocol_b,
    retire_seed,
    run_continuation,
)
from crucible.loop import LoopResult, ReproductionMismatch, RoundRecord

PROTOCOL_B = {
    "protocol_b_version": 1,
    "tester": {"provider": "anthropic", "model": "claude-sonnet-5"},
    "rounds": {"max_rounds": 4, "dry_rounds": 2},
    "replicates": {"k": 5, "max_seed_draws_per_replicate": 3,
                   "max_total_seed_draws_per_subject": 7},
    "seeds_dir": "experiments/seeds",
    "runs_dir": "experiments/runs-b",
    "arms": {
        "no-critic": {"mode": "seed-only"},
        "loop-same": {"mode": "seeded-harden",
                      "critic": {"provider": "anthropic", "model": "claude-sonnet-5"}},
        "loop-cross": {"mode": "seeded-harden",
                       "critic": {"provider": "openai", "model": "gpt-5.6-terra"}},
    },
    "subjects": {"subj": {"module": "pkg/mod.py"}},
}


def _write_protocol(tmp_path, data=None):
    p = tmp_path / "protocol-b.json"
    p.write_text(json.dumps(data or PROTOCOL_B))
    return p


# --- loader -------------------------------------------------------------------


def test_load_protocol_b_roundtrip(tmp_path):
    loaded = load_protocol_b(_write_protocol(tmp_path))
    assert loaded["replicates"]["k"] == 5
    assert loaded["arms"]["loop-cross"]["critic"]["model"] == "gpt-5.6-terra"


@pytest.mark.parametrize("missing", ["protocol_b_version", "replicates", "seeds_dir",
                                     "runs_dir", "arms", "subjects"])
def test_load_protocol_b_rejects_missing_key(tmp_path, missing):
    bad = {k: v for k, v in PROTOCOL_B.items() if k != missing}
    with pytest.raises(ProtocolBError, match=missing):
        load_protocol_b(_write_protocol(tmp_path, bad))


def test_load_protocol_b_rejects_bad_mode(tmp_path):
    bad = dict(PROTOCOL_B, arms={"x": {"mode": "harden"}})
    with pytest.raises(ProtocolBError, match="mode"):
        load_protocol_b(_write_protocol(tmp_path, bad))


def test_load_protocol_b_requires_exactly_one_seed_only_arm(tmp_path):
    none = dict(PROTOCOL_B, arms={"loop-same": PROTOCOL_B["arms"]["loop-same"]})
    with pytest.raises(ProtocolBError, match="seed-only"):
        load_protocol_b(_write_protocol(tmp_path, none))
    two = dict(PROTOCOL_B, arms=dict(PROTOCOL_B["arms"], extra={"mode": "seed-only"}))
    with pytest.raises(ProtocolBError, match="seed-only"):
        load_protocol_b(_write_protocol(tmp_path, two))


def test_load_protocol_b_seeded_harden_needs_critic(tmp_path):
    bad = dict(PROTOCOL_B, arms=dict(PROTOCOL_B["arms"], **{"loop-same": {"mode": "seeded-harden"}}))
    with pytest.raises(ProtocolBError, match="critic"):
        load_protocol_b(_write_protocol(tmp_path, bad))


@pytest.mark.parametrize("value", [0, -1, "5", None])
def test_load_protocol_b_rejects_non_positive_replicates(tmp_path, value):
    bad = dict(PROTOCOL_B, replicates=dict(PROTOCOL_B["replicates"], k=value))
    with pytest.raises(ProtocolBError, match="replicates.k"):
        load_protocol_b(_write_protocol(tmp_path, bad))


def test_load_protocol_b_rejects_subject_missing_module(tmp_path):
    bad = dict(PROTOCOL_B, subjects={"subj": {}})
    with pytest.raises(ProtocolBError, match="module"):
        load_protocol_b(_write_protocol(tmp_path, bad))


def test_repo_frozen_protocol_b_loads():
    # the actual frozen pre-registration must satisfy its own loader
    repo = Path(__file__).resolve().parents[1]
    loaded = load_protocol_b(repo / "experiments" / "protocol-b.json")
    assert loaded["replicates"]["k"] == 5
    assert set(loaded["subjects"]) == {"graph-guard", "rag-guard", "packaging", "idna"}
    assert loaded["analysis"] == {"bootstrap_draws": 10000, "rng_seed": 20260713}


# --- seed-dir commit gate -----------------------------------------------------


def _repo_with_seed(tmp_path, committed=True, extra_uncommitted=False, delete_after=False):
    repo = tmp_path / "crucible-repo"
    (repo / "seeds" / "subj" / "rep1").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    rep = repo / "seeds" / "subj" / "rep1"
    (rep / "seed_test.py").write_text("def test_x():\n    assert True\n")
    (rep / "seed.json").write_text("{}")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    if committed:
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "seed"], cwd=repo, check=True)
    if extra_uncommitted:
        (rep / "stray.txt").write_text("uncommitted")
    if delete_after:
        (rep / "seed.json").unlink()
    return repo, rep


def test_committed_seed_dir_passes(tmp_path):
    repo, rep = _repo_with_seed(tmp_path)
    assert_dir_committed(repo, rep)  # no raise


def test_uncommitted_seed_dir_refused(tmp_path):
    repo, rep = _repo_with_seed(tmp_path, committed=False)
    with pytest.raises(ProtocolBError):
        assert_dir_committed(repo, rep)


def test_modified_seed_file_refused(tmp_path):
    repo, rep = _repo_with_seed(tmp_path)
    (rep / "seed_test.py").write_text("def test_x():\n    assert False\n")
    with pytest.raises(ProtocolBError, match="differs from HEAD"):
        assert_dir_committed(repo, rep)


def test_stray_uncommitted_file_in_seed_dir_refused(tmp_path):
    repo, rep = _repo_with_seed(tmp_path, extra_uncommitted=True)
    with pytest.raises(ProtocolBError, match="differs from HEAD"):
        assert_dir_committed(repo, rep)


def test_file_deleted_from_disk_refused(tmp_path):
    repo, rep = _repo_with_seed(tmp_path, delete_after=True)
    with pytest.raises(ProtocolBError, match="differs from HEAD"):
        assert_dir_committed(repo, rep)


def test_empty_seed_dir_refused(tmp_path):
    repo = tmp_path / "crucible-repo"
    (repo / "seeds" / "subj" / "rep1").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    with pytest.raises(ProtocolBError, match="empty or missing"):
        assert_dir_committed(repo, repo / "seeds" / "subj" / "rep1")


# --- seed loading / retirement -------------------------------------------------


def _seed_dict(text="def test_a():\n    assert True\n", **over):
    import hashlib
    seed = {
        "subject": "subj", "rep": 1, "module": "pkg/mod.py", "head_sha": "abc123",
        "draw": 1, "baseline_survivors": ["m1", "m2", "m3"],
        "baseline_all_mutants": 10, "baseline_counts": {"survived": 3},
        "post_survivors": ["m3"],
        "post_counts": {"survived": 1},
        "test_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "provenance": {"model": "claude-sonnet-5", "prompt_sha256": "a" * 64,
                       "usage_in": 10, "usage_out": 5, "cost_usd": 0.01,
                       "dropped_tests": [], "generated_at": "20260713T000000Z"},
    }
    seed.update(over)
    return seed, text


def _write_seed(rep_dir, seed=None, text=None):
    default_seed, default_text = _seed_dict()
    seed = seed if seed is not None else default_seed
    text = text if text is not None else default_text
    rep_dir.mkdir(parents=True, exist_ok=True)
    (rep_dir / "seed.json").write_text(json.dumps(seed))
    (rep_dir / "seed_test.py").write_text(text)
    return seed, text


def test_load_seed_roundtrip(tmp_path):
    rep = tmp_path / "rep1"
    written, text = _write_seed(rep)
    seed, loaded_text = _load_seed(rep)
    assert seed["post_survivors"] == ["m3"]
    assert loaded_text == text


def test_load_seed_refuses_sha_mismatch(tmp_path):
    rep = tmp_path / "rep1"
    _write_seed(rep)
    (rep / "seed_test.py").write_text("def test_a():\n    assert 1\n")
    with pytest.raises(ProtocolBError, match="sha256"):
        _load_seed(rep)


def test_load_seed_refuses_missing(tmp_path):
    with pytest.raises(ProtocolBError, match="no frozen seed"):
        _load_seed(tmp_path / "rep1")


def test_retire_seed_keeps_draws_countable(tmp_path):
    seeds_root = tmp_path / "seeds"
    rep = seeds_root / "subj" / "rep1"
    _write_seed(rep)
    (rep / "draws" / "draw-1").mkdir(parents=True)
    assert retire_seed(seeds_root, "subj", 1, "reproduction mismatch") == 0
    assert not (rep / "seed.json").exists()
    assert not (rep / "seed_test.py").exists()
    assert list(rep.glob("seed-invalid-*.json"))
    assert list(rep.glob("retired-*.json"))
    # the retired replicate's draws still count against both caps (PROTOCOL-B §4)
    assert (rep / "draws" / "draw-1").exists()
    # and the replicate now reads as needing a (replacement) seed
    assert _next_rep_needing_seed(seeds_root / "subj", 5, 3) == 1


def test_next_rep_needing_seed_walks_in_order(tmp_path):
    subject = tmp_path / "subj"
    _write_seed(subject / "rep1")
    assert _next_rep_needing_seed(subject, 3, 3) == 2
    _write_seed(subject / "rep2")
    _write_seed(subject / "rep3")
    assert _next_rep_needing_seed(subject, 3, 3) is None


def test_next_rep_needing_seed_skips_cap_exhausted_replicate(tmp_path):
    # PROTOCOL-B §2: a seedless replicate with a spent 3-draw cap is MISSING;
    # it must never block the replicates behind it (review finding B1)
    subject = tmp_path / "subj"
    for n in (1, 2, 3):
        (subject / "rep1" / "draws" / f"draw-{n}").mkdir(parents=True)
    assert _next_rep_needing_seed(subject, 5, 3) == 2


# --- seed generation caps -------------------------------------------------------


class _SeedFakeEnv:
    def __init__(self, subject_dir):
        self.subject_dir = Path(subject_dir)
        self.tester_provider = type("P", (), {"billing": "api", "name": "anthropic"})()
        self.artifact_dir = None

    def reset_clone(self):
        pass

    def preflight(self, module_path):
        return "abc123"

    def set_artifact_dir(self, d):
        self.artifact_dir = d


def _fake_oneshot_result(verdict, subject_dir, kills=("m1", "m2")):
    rec = RoundRecord(round=0, role="tester", model="claude-sonnet-5",
                      prompt_sha256="a" * 64, usage_in=10, usage_out=5, cost_usd=0.01,
                      test_file="tests/crucible_r0_seed_test.py",
                      survivors_before=["m1", "m2", "m3"], survivors_after=["m3"],
                      kills=list(kills), all_mutants=10, counts={"survived": 1})
    (Path(subject_dir) / "tests").mkdir(parents=True, exist_ok=True)
    (Path(subject_dir) / rec.test_file).write_text("def test_a():\n    assert True\n")
    return LoopResult([rec], verdict, 0.01, baseline_survivors=["m1", "m2", "m3"],
                      baseline_all_mutants=10, baseline_counts={"survived": 3})


def _patch_seed_env(monkeypatch, subject_dir, verdict="oneshot"):
    import crucible.experiment_b as xb
    import crucible.loop as loop_mod

    monkeypatch.setattr(xb, "_make_env", lambda *a, **k: (_SeedFakeEnv(subject_dir), None))

    def fake_oneshot(env, cfg, on_round=None):
        result = _fake_oneshot_result(verdict, subject_dir)
        if on_round is not None:
            for rec in result.rounds:
                on_round(rec)
        return result

    monkeypatch.setattr(loop_mod, "oneshot", fake_oneshot)


def test_generate_seed_freezes_accepted_draw(tmp_path, monkeypatch):
    subject = tmp_path / "subj"
    subject.mkdir()
    seeds_root = tmp_path / "seeds"
    _patch_seed_env(monkeypatch, subject)
    assert generate_seed(PROTOCOL_B, subject, "pkg/mod.py", seeds_root) == 0
    rep = seeds_root / "subj" / "rep1"
    seed = json.loads((rep / "seed.json").read_text())
    assert seed["post_survivors"] == ["m3"]
    assert seed["baseline_survivors"] == ["m1", "m2", "m3"]
    assert seed["head_sha"] == "abc123"
    text = (rep / "seed_test.py").read_text()
    import hashlib
    assert seed["test_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    # draw receipted
    assert (rep / "draws" / "draw-1" / "receipt.jsonl").exists()


def test_generate_seed_rejected_draw_receipted_not_frozen(tmp_path, monkeypatch):
    subject = tmp_path / "subj"
    subject.mkdir()
    seeds_root = tmp_path / "seeds"
    _patch_seed_env(monkeypatch, subject, verdict="rejected")
    assert generate_seed(PROTOCOL_B, subject, "pkg/mod.py", seeds_root) == 3
    rep = seeds_root / "subj" / "rep1"
    assert not (rep / "seed.json").exists()
    assert (rep / "draws" / "draw-1" / "receipt.jsonl").exists()


def test_generate_seed_skips_cap_exhausted_rep_and_seeds_the_next(tmp_path, monkeypatch):
    # review finding B1: rep1's spent cap must not brick the subject
    subject = tmp_path / "subj"
    subject.mkdir()
    seeds_root = tmp_path / "seeds"
    for n in (1, 2, 3):
        (seeds_root / "subj" / "rep1" / "draws" / f"draw-{n}").mkdir(parents=True)
    _patch_seed_env(monkeypatch, subject)
    assert generate_seed(PROTOCOL_B, subject, "pkg/mod.py", seeds_root) == 0
    assert not (seeds_root / "subj" / "rep1" / "seed.json").exists()
    assert (seeds_root / "subj" / "rep2" / "seed.json").exists()


def test_generate_seed_reports_missing_when_all_seedless_reps_exhausted(tmp_path,
                                                                        monkeypatch, capsys):
    subject = tmp_path / "subj"
    subject.mkdir()
    seeds_root = tmp_path / "seeds"
    protocol = dict(PROTOCOL_B, replicates={"k": 2, "max_seed_draws_per_replicate": 3,
                                            "max_total_seed_draws_per_subject": 7})
    _write_seed(seeds_root / "subj" / "rep1")
    for n in (1, 2, 3):
        (seeds_root / "subj" / "rep2" / "draws" / f"draw-{n}").mkdir(parents=True)
    _patch_seed_env(monkeypatch, subject)
    assert generate_seed(protocol, subject, "pkg/mod.py", seeds_root) == 3
    out = capsys.readouterr().out
    assert "MISSING" in out and "[2]" in out


def test_generate_seed_enforces_subject_cap(tmp_path, monkeypatch):
    subject = tmp_path / "subj"
    subject.mkdir()
    seeds_root = tmp_path / "seeds"
    # 7 draws spread across replicates, none of which produced rep4's seed
    for rep, n in (("rep1", 3), ("rep2", 2), ("rep3", 2)):
        for i in range(1, n + 1):
            (seeds_root / "subj" / rep / "draws" / f"draw-{i}").mkdir(parents=True)
    for r in ("rep1", "rep2", "rep3"):
        _write_seed(seeds_root / "subj" / r)
    _patch_seed_env(monkeypatch, subject)
    with pytest.raises(ProtocolBError, match="7-draw cap"):
        generate_seed(PROTOCOL_B, subject, "pkg/mod.py", seeds_root)


def test_generate_seed_noop_when_all_reps_seeded(tmp_path, monkeypatch, capsys):
    subject = tmp_path / "subj"
    subject.mkdir()
    seeds_root = tmp_path / "seeds"
    for r in range(1, 6):
        _write_seed(seeds_root / "subj" / f"rep{r}")
    _patch_seed_env(monkeypatch, subject)
    assert generate_seed(PROTOCOL_B, subject, "pkg/mod.py", seeds_root) == 0
    assert "already have frozen seeds" in capsys.readouterr().out


def test_generate_seed_refuses_unknown_subject(tmp_path):
    with pytest.raises(ProtocolBError, match="not in protocol-b"):
        generate_seed(PROTOCOL_B, tmp_path / "other", "pkg/mod.py", tmp_path / "seeds")


def test_generate_seed_refuses_module_mismatch(tmp_path):
    subject = tmp_path / "subj"
    subject.mkdir()
    with pytest.raises(ProtocolBError, match="does not"):
        generate_seed(PROTOCOL_B, subject, "pkg/wrong.py", tmp_path / "seeds")


# --- continuations ---------------------------------------------------------------


def _continuation_repo(tmp_path):
    """A tmp crucible-repo with a committed frozen seed, plus a subject clone dir."""
    repo = tmp_path / "crucible-repo"
    rep = repo / "experiments" / "seeds" / "subj" / "rep1"
    rep.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    seed, text = _seed_dict()
    _write_seed(rep, seed, text)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "freeze seed"], cwd=repo, check=True)
    subject = tmp_path / "subj"
    (subject / "tests").mkdir(parents=True)
    return repo, rep, subject, seed


def test_no_critic_cell_is_derived_from_seed(tmp_path):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    runs_root = repo / "experiments" / "runs-b"
    rc = run_continuation(PROTOCOL_B, "no-critic", subject, "pkg/mod.py",
                          repo / "experiments" / "seeds", runs_root, repo, 1)
    assert rc == 0
    run_dir = next((runs_root / "subj").glob("no-critic-rep1-*"))
    result = json.loads((run_dir / "result.json").read_text())
    assert result["verdict"] == "oneshot"
    assert result["total_cost_usd"] == 0.0
    assert result["baseline_survivors"] == ["m1", "m2", "m3"]
    rounds = [json.loads(l) for l in
              (run_dir / "receipt.jsonl").read_text().strip().splitlines()]
    assert rounds[0]["kills"] == ["m1", "m2"]
    assert rounds[0]["cost_usd"] == 0.0
    meta = json.loads((run_dir / "meta.json").read_text())
    assert meta["seed"]["test_sha256"] == seed["test_sha256"]
    assert meta["derived"] is True


def test_no_critic_cell_refuses_uncommitted_seed(tmp_path):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    (rep / "seed_test.py").write_text("def test_a():\n    assert 2\n")  # drift after commit
    with pytest.raises(ProtocolBError, match="differs from HEAD"):
        run_continuation(PROTOCOL_B, "no-critic", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


class _ContinuationFakeEnv(_SeedFakeEnv):
    def __init__(self, subject_dir, head="abc123"):
        super().__init__(subject_dir)
        self._head = head

    def preflight(self, module_path):
        return self._head


def _patch_continuation(monkeypatch, subject, result=None, exc=None, head="abc123"):
    import crucible.experiment_b as xb
    import crucible.loop as loop_mod

    env = _ContinuationFakeEnv(subject, head=head)
    monkeypatch.setattr(xb, "_make_env", lambda *a, **k: (env, type("C", (), {"billing": "api"})()))

    def fake_seeded_run(env_, cfg, seed_text, base, post, on_round=None,
                        seed_model="", seed_prompt_sha256=""):
        if exc is not None:
            raise exc
        for rec in result.rounds:
            if on_round:
                on_round(rec)
        return result

    monkeypatch.setattr(loop_mod, "seeded_run", fake_seeded_run)
    return env


def test_seeded_continuation_happy_path(tmp_path, monkeypatch):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    (subject / "tests" / "crucible_r1_loop-same_test.py").write_text("def test_c(): pass\n")
    rec0 = RoundRecord(round=0, role="tester", survivors_before=["m1", "m2", "m3"],
                       survivors_after=["m3"], kills=["m1", "m2"], cost_usd=0.0)
    rec1 = RoundRecord(round=1, role="critic", survivors_before=["m3"],
                       survivors_after=[], kills=["m3"], cost_usd=0.02)
    result = LoopResult([rec0, rec1], "clean", 0.02,
                        baseline_survivors=["m1", "m2", "m3"],
                        baseline_all_mutants=10, baseline_counts={"survived": 3})
    _patch_continuation(monkeypatch, subject, result=result)
    rc = run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                          repo / "experiments" / "seeds",
                          repo / "experiments" / "runs-b", repo, 1)
    assert rc == 0
    run_dir = next((repo / "experiments" / "runs-b" / "subj").glob("loop-same-rep1-*"))
    result_json = json.loads((run_dir / "result.json").read_text())
    assert result_json["verdict"] == "clean"
    assert (run_dir / "accepted" / "crucible_r1_loop-same_test.py").exists()
    rounds = (run_dir / "receipt.jsonl").read_text().strip().splitlines()
    assert len(rounds) == 2


def test_seeded_continuation_reproduction_mismatch_is_invalid_exit_4(tmp_path, monkeypatch):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    billed = RoundRecord(round=1, role="critic", survivors_before=["m3"],
                         survivors_after=["m3"], cost_usd=0.05)
    _patch_continuation(monkeypatch, subject,
                        exc=ReproductionMismatch("post-round-0 survivors differ",
                                                 rounds=[billed]))
    rc = run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                          repo / "experiments" / "seeds",
                          repo / "experiments" / "runs-b", repo, 1)
    assert rc == 4
    run_dir = next((repo / "experiments" / "runs-b" / "subj").glob("loop-same-rep1-*"))
    result_json = json.loads((run_dir / "result.json").read_text())
    assert result_json["verdict"] == "invalid"
    assert "survivors differ" in result_json["invalid_reason"]
    # billed rounds are costed honestly even on an invalid cell
    assert result_json["total_cost_usd"] == pytest.approx(0.05)


def test_seeded_continuation_refuses_subject_head_drift(tmp_path, monkeypatch):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    _patch_continuation(monkeypatch, subject, head="OTHER")
    with pytest.raises(ProtocolBError, match="drifted"):
        run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


def test_seeded_continuation_refuses_module_mismatch_with_seed(tmp_path, monkeypatch):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    protocol = dict(PROTOCOL_B, subjects={"subj": {"module": "pkg/other.py"}})
    with pytest.raises(ProtocolBError, match="seed module"):
        run_continuation(protocol, "loop-same", subject, "pkg/other.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


def test_run_continuation_refuses_unknown_arm(tmp_path):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    with pytest.raises(ProtocolBError, match="arm"):
        run_continuation(PROTOCOL_B, "nope", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


def test_make_env_refuses_non_api_provider(monkeypatch, tmp_path):
    import crucible.experiment_b as xb

    class FakeProvider:
        billing = "max-plan"
        name = "claude-cli"

    monkeypatch.setattr(xb, "get_provider", lambda name: FakeProvider())
    with pytest.raises(ValueError, match="billing"):
        xb._make_env(PROTOCOL_B, PROTOCOL_B["tester"], tmp_path, "pkg/mod.py", {})


# --- dispatch (CLI arg contract + pre-registration gate) ---------------------------


class _Args:
    def __init__(self, **kw):
        self.protocol = kw.get("protocol")
        self.phase = kw.get("phase")
        self.subject = kw.get("subject", "subj")
        self.module = kw.get("module")
        self.arm = kw.get("arm")
        self.rep = kw.get("rep")
        self.reason = kw.get("reason")


def _committed_protocol_repo(tmp_path):
    repo = tmp_path / "crucible-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    p = repo / "protocol-b.json"
    p.write_text(json.dumps(PROTOCOL_B))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "freeze"], cwd=repo, check=True)
    return repo, p


def test_dispatch_refuses_uncommitted_protocol(tmp_path):
    from crucible.experiment import ProtocolError
    from crucible.experiment_b import dispatch
    repo, p = _committed_protocol_repo(tmp_path)
    p.write_text(json.dumps(dict(PROTOCOL_B, protocol_b_version=2)))  # drift after commit
    with pytest.raises(ProtocolError, match="differs from HEAD"):
        dispatch(_Args(protocol=str(p), phase="seed", module="pkg/mod.py"), repo)


@pytest.mark.parametrize("phase,kw,msg", [
    ("seed", {}, "--module"),
    ("run", {"module": "pkg/mod.py", "rep": 1}, "--arm"),
    ("run", {"module": "pkg/mod.py", "arm": "loop-same"}, "--rep"),
    ("run", {"arm": "loop-same", "rep": 1}, "--module"),
    ("retire-seed", {"rep": 1}, "--reason"),
    ("retire-seed", {"reason": "mismatch"}, "--rep"),
])
def test_dispatch_arg_contract(tmp_path, phase, kw, msg):
    from crucible.experiment_b import dispatch
    repo, p = _committed_protocol_repo(tmp_path)
    with pytest.raises(ProtocolBError, match=msg):
        dispatch(_Args(protocol=str(p), phase=phase, **kw), repo)


# --- §7/§8 rerun gate (review finding B2) ------------------------------------------


def _prior_cell(repo, arm, rep, verdict=None, name_stamp="20260713T000000Z",
                seed_sha=None, write_meta=True):
    d = repo / "experiments" / "runs-b" / "subj" / f"{arm}-rep{rep}-{name_stamp}"
    d.mkdir(parents=True)
    if write_meta:
        sha = seed_sha if seed_sha is not None else _seed_dict()[0]["test_sha256"]
        (d / "meta.json").write_text(json.dumps({"seed": {"test_sha256": sha}}))
    if verdict is not None:
        (d / "result.json").write_text(json.dumps({"verdict": verdict,
                                                   "total_cost_usd": 0.1}))
    return d


@pytest.mark.parametrize("verdict", ["clean", "dry", "cap", "oneshot"])
def test_validly_scored_cell_is_never_rerun(tmp_path, verdict):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    _prior_cell(repo, "loop-same", 1, verdict)
    with pytest.raises(ProtocolBError, match="never rerun"):
        run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


def test_invalid_cell_routes_to_seed_retirement_not_rerun(tmp_path):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    _prior_cell(repo, "loop-same", 1, "invalid")
    with pytest.raises(ProtocolBError, match="retire the seed"):
        run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


def test_single_abort_permits_exactly_one_rerun(tmp_path, monkeypatch, capsys):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    _prior_cell(repo, "loop-same", 1, "aborted")
    rec0 = RoundRecord(round=0, role="tester", survivors_before=["m1", "m2", "m3"],
                       survivors_after=["m3"], kills=["m1", "m2"], cost_usd=0.0)
    result = LoopResult([rec0], "dry", 0.0, baseline_survivors=["m1", "m2", "m3"],
                        baseline_all_mutants=10, baseline_counts={"survived": 3})
    _patch_continuation(monkeypatch, subject, result=result)
    rc = run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                          repo / "experiments" / "seeds",
                          repo / "experiments" / "runs-b", repo, 1)
    assert rc == 0
    assert "single mandatory" in capsys.readouterr().out


def test_second_abort_scores_the_cell_missing(tmp_path):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    _prior_cell(repo, "loop-same", 1, "aborted", name_stamp="20260713T000000Z")
    _prior_cell(repo, "loop-same", 1, "aborted", name_stamp="20260713T010000Z")
    with pytest.raises(ProtocolBError, match="MISSING"):
        run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


def test_crashed_cell_without_result_json_counts_as_an_abort(tmp_path):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    _prior_cell(repo, "loop-same", 1, None, name_stamp="20260713T000000Z")  # crashed
    _prior_cell(repo, "loop-same", 1, "aborted", name_stamp="20260713T010000Z")
    with pytest.raises(ProtocolBError, match="MISSING"):
        run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


def test_metaless_cell_dir_counts_as_an_abort_for_the_current_seed(tmp_path):
    # a dir with no meta.json cannot come from a real run; the gate treats it as
    # an abort-class attempt for THIS seed rather than ignoring it (conservative)
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    _prior_cell(repo, "loop-same", 1, None, name_stamp="20260713T000000Z",
                write_meta=False)
    _prior_cell(repo, "loop-same", 1, "aborted", name_stamp="20260713T010000Z")
    with pytest.raises(ProtocolBError, match="MISSING"):
        run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


def test_retired_seeds_receipts_do_not_block_the_replacement_seed(tmp_path, monkeypatch):
    # review finding B3: after §4 retirement + replacement, the OLD seed's scored
    # and invalid receipts are DEVIATIONS material -- the replacement seed's
    # continuations must run. Receipts under the SAME seed still refuse (§8).
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    # prior receipts belong to a different (retired) seed
    _prior_cell(repo, "loop-same", 1, "dry", name_stamp="20260713T000000Z",
                seed_sha="0" * 64)
    _prior_cell(repo, "loop-same", 1, "invalid", name_stamp="20260713T010000Z",
                seed_sha="0" * 64)
    rec0 = RoundRecord(round=0, role="tester", survivors_before=["m1", "m2", "m3"],
                       survivors_after=["m3"], kills=["m1", "m2"], cost_usd=0.0)
    result = LoopResult([rec0], "dry", 0.0, baseline_survivors=["m1", "m2", "m3"],
                        baseline_all_mutants=10, baseline_counts={"survived": 3})
    _patch_continuation(monkeypatch, subject, result=result)
    rc = run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                          repo / "experiments" / "seeds",
                          repo / "experiments" / "runs-b", repo, 1)
    assert rc == 0                        # replacement seed's cell runs
    with pytest.raises(ProtocolBError, match="never rerun"):
        run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


def test_no_critic_cell_is_not_rerunnable_either(tmp_path):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    rc = run_continuation(PROTOCOL_B, "no-critic", subject, "pkg/mod.py",
                          repo / "experiments" / "seeds",
                          repo / "experiments" / "runs-b", repo, 1)
    assert rc == 0
    with pytest.raises(ProtocolBError, match="never rerun"):
        run_continuation(PROTOCOL_B, "no-critic", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 1)


# --- remaining review findings ------------------------------------------------------


def test_aborted_seeded_continuation_returns_3(tmp_path, monkeypatch):
    # review finding S3: exit 3 is the operator's §7 rerun trigger
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    rec0 = RoundRecord(round=0, role="tester", survivors_before=["m1", "m2", "m3"],
                       survivors_after=["m3"], kills=["m1", "m2"], cost_usd=0.0)
    rec1 = RoundRecord(round=1, role="critic", survivors_before=["m3"],
                       survivors_after=["m3"], status="aborted", cost_usd=0.0)
    result = LoopResult([rec0, rec1], "aborted", 0.0,
                        baseline_survivors=["m1", "m2", "m3"],
                        baseline_all_mutants=10, baseline_counts={"survived": 3})
    _patch_continuation(monkeypatch, subject, result=result)
    rc = run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                          repo / "experiments" / "seeds",
                          repo / "experiments" / "runs-b", repo, 1)
    assert rc == 3


def test_no_critic_round_counts_come_from_frozen_post_counts(tmp_path):
    # review finding S2: the derived cell must carry the seed's post-measure
    # counts, never the baseline's (which would be internally false)
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    rc = run_continuation(PROTOCOL_B, "no-critic", subject, "pkg/mod.py",
                          repo / "experiments" / "seeds",
                          repo / "experiments" / "runs-b", repo, 1)
    assert rc == 0
    run_dir = next((repo / "experiments" / "runs-b" / "subj").glob("no-critic-rep1-*"))
    rounds = [json.loads(l) for l in
              (run_dir / "receipt.jsonl").read_text().strip().splitlines()]
    assert rounds[0]["counts"] == {"survived": 1}          # post, not {"survived": 3}


def test_load_seed_refuses_missing_post_counts(tmp_path):
    rep = tmp_path / "rep1"
    seed, text = _seed_dict()
    del seed["post_counts"]
    _write_seed(rep, seed, text)
    with pytest.raises(ProtocolBError, match="post_counts"):
        _load_seed(rep)


def test_run_continuation_bounds_rep_to_pre_registered_range(tmp_path):
    repo, rep, subject, seed = _continuation_repo(tmp_path)
    with pytest.raises(ProtocolBError, match="1..5"):
        run_continuation(PROTOCOL_B, "loop-same", subject, "pkg/mod.py",
                         repo / "experiments" / "seeds",
                         repo / "experiments" / "runs-b", repo, 6)


def test_dispatch_refuses_rep_for_seed_phase(tmp_path):
    from crucible.experiment_b import dispatch
    repo, p = _committed_protocol_repo(tmp_path)
    with pytest.raises(ProtocolBError, match="auto-selected"):
        dispatch(_Args(protocol=str(p), phase="seed", module="pkg/mod.py", rep=2), repo)


@pytest.mark.parametrize("field,value", [("max_rounds", 0), ("dry_rounds", "2")])
def test_load_protocol_b_rejects_malformed_rounds(tmp_path, field, value):
    bad = dict(PROTOCOL_B, rounds=dict(PROTOCOL_B["rounds"], **{field: value}))
    with pytest.raises(ProtocolBError, match=f"rounds.{field}"):
        load_protocol_b(_write_protocol(tmp_path, bad))
