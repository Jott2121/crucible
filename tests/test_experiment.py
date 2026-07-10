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
