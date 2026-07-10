#!/usr/bin/env python3
"""Free scope validator -- the check that should have existed before the H1 grid ran.

For each subject in `experiments/protocol.json`'s `subjects` map: reset the clone to its
committed HEAD (same semantics as `crucible.env.SubjectEnv.reset_clone`), apply the frozen
[tool.mutmut] scope exactly as `crucible experiment` would at preflight (the real
`SubjectEnv.preflight`, not a reimplementation), run `python -m mutmut run` for real, and
parse the result through `crucible.engine.MutmutEngine.measure` (the same oracle-gate
parser the real experiment uses). Compare the measured (mutants, killed, survived) against
subjects.json's recorded smoke counts and print a table.

$0 always: no model provider is ever constructed or called (FakeProvider, never invoked --
this script never calls .call_tester()/.call_critic()).

A mismatch in mutant COUNT means the frozen scope is wrong (wrong file, missing also_copy)
-- that always fails the run. A mismatch in the killed/survived SPLIT is expected and
correct for subjects whose test suite is deliberately stripped for the real experiment
(protocol.json/subjects.json strip_tests=true): the smoke count was measured at selection
time against that subject's OWN (unstripped) suite, while the real pristine baseline is
measured against a genuinely empty suite (PROTOCOL.md §3: "scored against a genuinely
empty starting suite") -- 0 killed is then the correct, designed outcome, not a bug
(PROTOCOL.md §3 amendment, protocol_version 4). This script treats that case as a
documented pass, not a silent one -- see the "note" column.

Usage: .venv/bin/python experiments/validate_scopes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from crucible.env import SubjectEnv  # noqa: E402
from crucible.providers_ext import FakeProvider  # noqa: E402

PROTOCOL_JSON = REPO_ROOT / "experiments" / "protocol.json"
SUBJECTS_JSON = REPO_ROOT / "experiments" / "subjects.json"
CRUCIBLE_SUBJECTS = Path.home() / "crucible-subjects"


def _load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _smoke_str(smoke: dict) -> str:
    return f"{smoke['mutants']}m {smoke['killed']}k {smoke['survived']}s"


def _measured_str(all_mutants: int, killed: int, survived: int) -> str:
    return f"{all_mutants}m {killed}k {survived}s"


def validate_subject(name: str, scope: dict, meta: dict | None) -> tuple[str, str, str, str, str]:
    """Returns (subject, expected, measured, verdict, note)."""
    if meta is None:
        return (name, "?", "-", "MISMATCH", "no subjects.json entry for this subject")

    clone_dir = CRUCIBLE_SUBJECTS / name
    if not clone_dir.exists():
        return (name, _smoke_str(meta["smoke"]), "-", "MISMATCH", f"clone missing: {clone_dir}")

    env = SubjectEnv(
        subject_dir=clone_dir,
        tester_provider=FakeProvider([]), tester_model="fake-model",
        critic_provider=FakeProvider([]), critic_model="fake-model",
        module_path=scope["module"], scope=scope,
    )
    try:
        env.reset_clone()
        env.preflight(scope["module"])
        outcome = env.measure()
    except Exception as exc:  # noqa: BLE001 -- report every subject, don't abort the sweep
        return (name, _smoke_str(meta["smoke"]), "-", "MISMATCH", f"{type(exc).__name__}: {exc}")

    measured_mutants = outcome.all_mutants
    measured_killed = outcome.counts.get("killed", 0)
    measured_survived = len(outcome.survivors)
    measured = _measured_str(measured_mutants, measured_killed, measured_survived)

    smoke = meta["smoke"]
    stripped = meta.get("strip_tests", False)

    mutants_match = measured_mutants == smoke["mutants"]
    if stripped:
        # protocol §3 / §3 amendment (v4): a stripped subject's real pristine
        # baseline is measured against zero tests, so 0 killed / all-survived
        # is the designed outcome -- the smoke count (measured against the
        # subject's own unstripped suite at selection time) is not expected
        # to match the split. Only the mutant COUNT validates the scope here.
        split_ok = measured_killed == 0 and measured_survived == measured_mutants
        note = ("stripped-suite baseline: 0 killed by design (protocol §3)"
                if split_ok else "inconsistent stripped-suite baseline (not 0 killed / all-survived)")
    else:
        split_ok = measured_killed == smoke["killed"] and measured_survived == smoke["survived"]
        note = "" if split_ok else "kill/survive split differs from smoke -- investigate, do not paper over"

    ok = mutants_match and split_ok
    if not mutants_match:
        note = (f"mutant count differs from smoke ({measured_mutants} vs {smoke['mutants']}) "
                 "-- scope is wrong, not a stripped-suite artifact")
    verdict = "MATCH" if ok else "MISMATCH"
    return (name, _smoke_str(smoke), measured, verdict, note)


def _print_table(rows: list[tuple[str, ...]]) -> None:
    header = ("subject", "expected", "measured", "verdict", "note")
    all_rows = [header, *rows]
    widths = [max(len(str(r[i])) for r in all_rows) for i in range(len(header))]

    def fmt(row):
        return " | ".join(str(cell).ljust(w) for cell, w in zip(row, widths))

    print(fmt(header))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt(row))


def main() -> int:
    protocol = _load(PROTOCOL_JSON)
    subjects_meta = {s["name"]: s for s in _load(SUBJECTS_JSON)["subjects"]}
    scopes = protocol.get("subjects", {})
    if not scopes:
        print("experiments/protocol.json has no 'subjects' scope map; nothing to validate")
        return 1

    rows = [validate_subject(name, scope, subjects_meta.get(name)) for name, scope in scopes.items()]
    _print_table(rows)

    mismatches = [r for r in rows if r[3] != "MATCH"]
    print()
    if mismatches:
        print(f"{len(mismatches)}/{len(rows)} subject(s) MISMATCH: "
              f"{', '.join(r[0] for r in mismatches)}")
        return 1
    print(f"{len(rows)}/{len(rows)} subjects MATCH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
