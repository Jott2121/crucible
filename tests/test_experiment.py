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
