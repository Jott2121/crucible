import json
import subprocess
from pathlib import Path

import pytest

from crucible.experiment import ProtocolError, assert_protocol_committed, load_protocol

PROTOCOL = {
    "protocol_version": 1,
    "tester": {"provider": "anthropic", "model": "claude-sonnet-5"},
    "rounds": {"max_rounds": 4, "dry_rounds": 2},
    "arms": {
        "oneshot": {"mode": "oneshot"},
        "loop-same": {"mode": "harden", "critic": {"provider": "anthropic", "model": "claude-sonnet-5"}},
        "loop-cross": {"mode": "harden", "critic": {"provider": "openai", "model": "gpt-5.6"}},
    },
}


def test_load_protocol_roundtrip(tmp_path):
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(PROTOCOL))
    loaded = load_protocol(p)
    assert loaded["arms"]["loop-cross"]["critic"]["model"] == "gpt-5.6"


def test_load_protocol_rejects_unknown_arm_mode(tmp_path):
    bad = dict(PROTOCOL, arms={"x": {"mode": "yolo"}})
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ProtocolError, match="mode"):
        load_protocol(p)


def _git_repo_with(tmp_path, name, content, committed=True):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    f = repo / name
    f.write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    if committed:
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "seed"], cwd=repo, check=True)
    return repo, f


def test_committed_protocol_passes(tmp_path):
    repo, f = _git_repo_with(tmp_path, "protocol.json", json.dumps(PROTOCOL))
    assert_protocol_committed(repo, f)  # no raise


def test_uncommitted_protocol_refused(tmp_path):
    repo, f = _git_repo_with(tmp_path, "protocol.json", json.dumps(PROTOCOL), committed=False)
    with pytest.raises(ProtocolError, match="committed"):
        assert_protocol_committed(repo, f)


def test_modified_protocol_refused(tmp_path):
    repo, f = _git_repo_with(tmp_path, "protocol.json", json.dumps(PROTOCOL))
    f.write_text(json.dumps(dict(PROTOCOL, protocol_version=2)))
    with pytest.raises(ProtocolError, match="differs from HEAD"):
        assert_protocol_committed(repo, f)


PROTOCOL_V2 = dict(
    PROTOCOL,
    protocol_version=2,
    subjects={
        "graph-guard": {
            "module": "graph_guard/ppr.py",
            "also_copy": ["graph_guard"],
            "pytest_args": ["tests/test_ppr.py"],
        },
        "rag-guard": {"module": "rag_guard/guard.py", "also_copy": ["rag_guard"]},
    },
)


def test_load_protocol_v2_accepts_subjects_map(tmp_path):
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(PROTOCOL_V2))
    loaded = load_protocol(p)
    assert loaded["subjects"]["graph-guard"]["also_copy"] == ["graph_guard"]
    assert loaded["subjects"]["rag-guard"]["module"] == "rag_guard/guard.py"


def test_load_protocol_rejects_subject_missing_module(tmp_path):
    bad = dict(PROTOCOL_V2, subjects={"graph-guard": {"also_copy": ["graph_guard"]}})
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ProtocolError, match="module"):
        load_protocol(p)


def test_load_protocol_v1_without_subjects_still_works(tmp_path):
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(PROTOCOL))
    loaded = load_protocol(p)
    assert "subjects" not in loaded


# --- v7: optional per-subject extra_files / import_hint fields ---

PROTOCOL_V7 = dict(
    PROTOCOL,
    protocol_version=7,
    subjects={
        "attrition-risk-ml": {
            "module": "src/train.py",
            "also_copy": ["src", "data"],
            "extra_files": {"conftest.py": "import sys\n"},
            "import_hint": "Import as `import train`, not `import src.train`.",
        },
        "rag-guard": {"module": "rag_guard/guard.py", "also_copy": ["rag_guard"]},
    },
)


def test_load_protocol_v7_accepts_extra_files_and_import_hint(tmp_path):
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(PROTOCOL_V7))
    loaded = load_protocol(p)
    scope = loaded["subjects"]["attrition-risk-ml"]
    assert scope["extra_files"] == {"conftest.py": "import sys\n"}
    assert scope["import_hint"] == "Import as `import train`, not `import src.train`."


def test_load_protocol_v7_subject_without_new_fields_still_works(tmp_path):
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(PROTOCOL_V7))
    loaded = load_protocol(p)
    scope = loaded["subjects"]["rag-guard"]
    assert "extra_files" not in scope and "import_hint" not in scope


def test_load_protocol_rejects_non_dict_extra_files(tmp_path):
    bad = dict(PROTOCOL_V7, subjects={
        "attrition-risk-ml": {"module": "src/train.py", "extra_files": ["conftest.py"]},
    })
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ProtocolError, match="extra_files"):
        load_protocol(p)


def test_load_protocol_rejects_extra_files_with_non_string_content(tmp_path):
    bad = dict(PROTOCOL_V7, subjects={
        "attrition-risk-ml": {"module": "src/train.py", "extra_files": {"conftest.py": 123}},
    })
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ProtocolError, match="extra_files"):
        load_protocol(p)


def test_load_protocol_rejects_non_string_import_hint(tmp_path):
    bad = dict(PROTOCOL_V7, subjects={
        "attrition-risk-ml": {"module": "src/train.py", "import_hint": ["not", "a", "string"]},
    })
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ProtocolError, match="import_hint"):
        load_protocol(p)


PROTOCOL_FOR_RUN_ARM = {
    "protocol_version": 2,
    "tester": {"provider": "fake", "model": "fake-model"},
    "rounds": {"max_rounds": 4, "dry_rounds": 2},
    "arms": {"oneshot": {"mode": "oneshot"}},
    "subjects": {
        "graph-guard": {"module": "graph_guard/ppr.py", "also_copy": ["graph_guard"]},
    },
}


def test_run_arm_raises_protocol_error_when_subject_not_in_protocol(tmp_path):
    from crucible.experiment import run_arm

    with pytest.raises(ProtocolError, match="not in protocol"):
        run_arm(PROTOCOL_FOR_RUN_ARM, "oneshot", tmp_path / "unknown-subject",
                tmp_path / "runs", "some/module.py")


def test_run_arm_raises_protocol_error_on_module_mismatch(tmp_path):
    from crucible.experiment import run_arm

    with pytest.raises(ProtocolError, match="does not match"):
        run_arm(PROTOCOL_FOR_RUN_ARM, "oneshot", tmp_path / "graph-guard",
                tmp_path / "runs", "graph_guard/wrong.py")


def test_run_arm_wires_the_run_dir_into_env_set_artifact_dir(tmp_path, monkeypatch):
    # run_arm must call env.set_artifact_dir(run_dir) right after creating the writer,
    # so a rejected/salvaged test file lands under this cell's own receipt directory
    # (rejected-artifact preservation, v3) rather than being silently discarded.
    from crucible import env as env_module
    from crucible.engine import MutationOutcome
    from crucible.experiment import run_arm
    from crucible.loop import RoundReply

    calls = {}

    class FakeSubjectEnv:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def reset_clone(self):
            pass

        def preflight(self, module_path):
            return "a" * 40

        def set_artifact_dir(self, run_dir):
            calls["artifact_dir"] = run_dir

        def measure(self):
            return MutationOutcome(counts={"survived": 0}, survivors=[], all_mutants=0)

        def call_tester(self):
            from oracle_gate.providers import Usage
            return RoundReply("```python\nassert True\n```", "a" * 64, "fake-model", Usage(1, 1))

        def write_test_file(self, round_no, arm, content):
            return f"tests/crucible_r{round_no}_{arm}_test.py"

        def validate(self, test_path):
            return []

        def remove_test_file(self, path):
            pass

        def assert_clean(self):
            pass

        def cost_usd(self, model, usage):
            return 0.0

    monkeypatch.setattr(env_module, "SubjectEnv", FakeSubjectEnv)

    subject_dir = tmp_path / "graph-guard"
    subject_dir.mkdir()
    # Create a dummy accepted test file to verify archiving.
    tests_dir = subject_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "crucible_r0_oneshot_test.py").write_text("# accepted test file\n")

    run_arm(PROTOCOL_FOR_RUN_ARM, "oneshot", subject_dir,
            tmp_path / "runs", "graph_guard/ppr.py")

    assert "artifact_dir" in calls
    run_dir = calls["artifact_dir"]
    assert run_dir.parent == tmp_path / "runs" / "graph-guard"
    assert run_dir.name.startswith("oneshot-")
    # set_artifact_dir must be called BEFORE any round runs, so a round-0 rejection
    # has somewhere to land -- the receipt dir must already exist on disk by then.
    assert run_dir.exists()
    # Accepted test files must be archived into run_dir/accepted after the run finishes.
    accepted_file = run_dir / "accepted" / "crucible_r0_oneshot_test.py"
    assert accepted_file.exists()
    assert accepted_file.read_text() == "# accepted test file\n"


def test_run_arm_resets_the_clone_before_preflight(tmp_path, monkeypatch):
    # Cell isolation (v3 fix): sequential cells share a subject clone. The previous
    # cell's accepted crucible_ test files are left untracked in the clone, so the
    # next cell's preflight would otherwise correctly refuse "subject clone is
    # dirty". run_arm must call env.reset_clone() before env.preflight(), never after.
    from crucible import env as env_module
    from crucible.engine import MutationOutcome
    from crucible.experiment import run_arm
    from crucible.loop import RoundReply

    order = []

    class FakeSubjectEnv:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def reset_clone(self):
            order.append("reset_clone")

        def preflight(self, module_path):
            order.append("preflight")
            return "a" * 40

        def set_artifact_dir(self, run_dir):
            pass

        def measure(self):
            return MutationOutcome(counts={"survived": 0}, survivors=[], all_mutants=0)

        def call_tester(self):
            from oracle_gate.providers import Usage
            return RoundReply("```python\nassert True\n```", "a" * 64, "fake-model", Usage(1, 1))

        def write_test_file(self, round_no, arm, content):
            return f"tests/crucible_r{round_no}_{arm}_test.py"

        def validate(self, test_path):
            return []

        def remove_test_file(self, path):
            pass

        def assert_clean(self):
            pass

        def cost_usd(self, model, usage):
            return 0.0

    monkeypatch.setattr(env_module, "SubjectEnv", FakeSubjectEnv)

    run_arm(PROTOCOL_FOR_RUN_ARM, "oneshot", tmp_path / "graph-guard",
            tmp_path / "runs", "graph_guard/ppr.py")

    assert order == ["reset_clone", "preflight"]


def test_run_arm_refuses_non_api_provider(monkeypatch, tmp_path):
    """Pre-registered runs demand metered, receipt-exact spend; a plan-covered
    provider must be refused BEFORE any run dir exists (spec 2026-07-11 §5)."""
    import crucible.experiment as exp

    class MaxPlanFake:
        billing = "max-plan"
        name = "claude-cli"

        def complete_with_usage(self, *a, **k):
            raise AssertionError("must never be called")

    monkeypatch.setattr(exp, "get_provider", lambda name: MaxPlanFake())
    protocol = dict(PROTOCOL_FOR_RUN_ARM, tester={"provider": "claude-cli", "model": "claude-sonnet-5"})
    with pytest.raises(ValueError, match="max-plan"):
        exp.run_arm(protocol, "oneshot", tmp_path / "graph-guard",
                    tmp_path / "runs", "graph_guard/ppr.py")
    assert not (tmp_path / "runs").exists() or not any((tmp_path / "runs").iterdir())
