"""Receipts: one JSONL line per round, appended durably as the loop runs.

meta.json binds the run to the subject's commit SHA and the exact config; receipt.jsonl
carries the per-round evidence (prompt hashes, usage, kills); result.json is the verdict.
A crash loses at most the in-flight round (error-swallowing lesson: never buffer a run's
evidence in memory).
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path


class ReceiptWriter:
    def __init__(self, run_dir, meta: dict):
        self.run_dir = Path(run_dir)
        # A reused run_dir would interleave two runs' receipt lines; refuse loudly.
        self.run_dir.mkdir(parents=True, exist_ok=False)
        (self.run_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    def append(self, record) -> None:
        line = json.dumps(dataclasses.asdict(record))
        with open(self.run_dir / "receipt.jsonl", "a") as f:
            f.write(line + "\n")

    def finish(self, verdict: str, total_cost_usd: float) -> None:
        (self.run_dir / "result.json").write_text(
            json.dumps({"verdict": verdict, "total_cost_usd": total_cost_usd})
        )


def load_run(run_dir) -> dict:
    run_dir = Path(run_dir)
    rounds = []
    receipt = run_dir / "receipt.jsonl"
    if receipt.exists():
        rounds = [json.loads(l) for l in receipt.read_text().strip().splitlines() if l]
    result = None
    if (run_dir / "result.json").exists():
        result = json.loads((run_dir / "result.json").read_text())
    return {
        "meta": json.loads((run_dir / "meta.json").read_text()),
        "rounds": rounds,
        "result": result,
    }
