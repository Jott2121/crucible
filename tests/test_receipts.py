import json

import pytest

from crucible.loop import RoundRecord
from crucible.receipts import ReceiptWriter, load_run


def test_receipt_roundtrip(tmp_path):
    w = ReceiptWriter(tmp_path / "run1", {"subject": "graph-guard", "head_sha": "abc123", "arm": "loop"})
    w.append(RoundRecord(round=0, role="tester", kills=[], survivors_after=["m1"]))
    w.append(RoundRecord(round=1, role="critic", kills=["m1"], survivors_after=[]))
    w.finish("clean", 0.42)

    run = load_run(tmp_path / "run1")
    assert run["meta"]["head_sha"] == "abc123"
    assert [r["round"] for r in run["rounds"]] == [0, 1]
    assert run["rounds"][1]["kills"] == ["m1"]
    assert run["result"] == {"verdict": "clean", "total_cost_usd": 0.42}


def test_append_is_durable_per_round(tmp_path):
    w = ReceiptWriter(tmp_path / "run2", {"subject": "s", "head_sha": "x", "arm": "oneshot"})
    w.append(RoundRecord(round=0, role="tester"))
    # no finish() — simulate a crash; the round must still be on disk
    lines = (tmp_path / "run2" / "receipt.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["role"] == "tester"


def test_run_dir_reuse_fails_loud(tmp_path):
    ReceiptWriter(tmp_path / "run3", {"a": 1})
    with pytest.raises(FileExistsError):
        ReceiptWriter(tmp_path / "run3", {"a": 1})
