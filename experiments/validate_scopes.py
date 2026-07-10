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

Canary must-kill probe (protocol_version 6, PROTOCOL.md §3.2 v6 amendment): the count-match
check above proves the mutant DENOMINATOR is right, but it does NOT prove mutmut's stats
phase ever actually collects a freshly-written `tests/crucible_*_test.py` file -- exactly
the gap that made rag-guard's (and, this amendment discovered, graph-guard's) counted H1
cells instrument-invalid under the v5 include-list `pytest_args` (DEVIATIONS.md). After the
count-match check, this script writes each subject's `protocol.json["canary"]` body to
`tests/crucible_canary_test.py` in the clone, confirms it passes pristine on its own (a
failing canary is this script's bug, not the subject's -- never trusted un-verified), then
runs mutmut for real a second time and compares the measured killed count against the
count-match check's own baseline. `killed` increasing proves the canary file was collected
and its assertion actually reached mutmut's oracle; `killed` staying flat (delta 0) proves
it was not collected at all, no matter what it asserts -- the exact rag-guard/graph-guard
failure mode. Verdict is KILLS/NO-KILLS, not a raw count, because the informative fact is
the delta, not the absolute number (an already-covered subject's pre-existing suite can
supply a large nonzero killed count with or without the canary ever running).

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

CANARY_REL_PATH = Path("tests") / "crucible_canary_test.py"


def _load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _smoke_str(smoke: dict) -> str:
    return f"{smoke['mutants']}m {smoke['killed']}k {smoke['survived']}s"


def _measured_str(all_mutants: int, killed: int, survived: int) -> str:
    return f"{all_mutants}m {killed}k {survived}s"


def _make_env(clone_dir: Path, scope: dict) -> SubjectEnv:
    return SubjectEnv(
        subject_dir=clone_dir,
        tester_provider=FakeProvider([]), tester_model="fake-model",
        critic_provider=FakeProvider([]), critic_model="fake-model",
        module_path=scope["module"], scope=scope,
    )


def validate_subject(name: str, scope: dict, meta: dict | None) -> tuple[tuple, int | None, Path | None]:
    """Returns (row, baseline_killed, clone_dir). baseline_killed/clone_dir are None when
    the subject can't even be measured -- the canary probe is skipped for that subject."""
    if meta is None:
        return (name, "?", "-", "MISMATCH", "no subjects.json entry for this subject"), None, None

    clone_dir = CRUCIBLE_SUBJECTS / name
    if not clone_dir.exists():
        return (name, _smoke_str(meta["smoke"]), "-", "MISMATCH", f"clone missing: {clone_dir}"), None, None

    env = _make_env(clone_dir, scope)
    try:
        env.reset_clone()
        env.preflight(scope["module"])
        outcome = env.measure()
    except Exception as exc:  # noqa: BLE001 -- report every subject, don't abort the sweep
        return (name, _smoke_str(meta["smoke"]), "-", "MISMATCH", f"{type(exc).__name__}: {exc}"), None, None

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
    elif measured_killed > smoke["killed"] and measured_survived < smoke["survived"]:
        # v6 amendment (PROTOCOL.md §3.2): converting an include-list pytest_args to
        # exclude-form (--ignore=...) can only WIDEN what mutmut's stats phase
        # collects relative to the old, narrower positional-arg form the smoke count
        # was measured under -- it never removes real coverage. A rag-guard-shaped
        # subject whose old include-list named exactly one test file now also picks
        # up every OTHER pre-existing test file that happens to exercise the mutated
        # module (previously silently excluded, same mechanism as the crucible_*
        # generated files this amendment exists to fix). More kills than smoke, never
        # fewer, is the expected signature of that widening -- a strictly-worse
        # (fewer kills) split still fails loud below.
        split_ok = True
        note = (f"widened-scope kill increase over smoke ({measured_killed} vs "
                 f"{smoke['killed']}k) -- exclude-form now also collects pre-existing "
                 "test files the old include-list silently dropped (v6 amendment)")
    else:
        split_ok = measured_killed == smoke["killed"] and measured_survived == smoke["survived"]
        note = "" if split_ok else "kill/survive split differs from smoke -- investigate, do not paper over"

    ok = mutants_match and split_ok
    if not mutants_match:
        note = (f"mutant count differs from smoke ({measured_mutants} vs {smoke['mutants']}) "
                 "-- scope is wrong, not a stripped-suite artifact")
    verdict = "MATCH" if ok else "MISMATCH"
    row = (name, _smoke_str(smoke), measured, verdict, note)
    return row, measured_killed, clone_dir


def run_canary_probe(name: str, scope: dict, clone_dir: Path, baseline_killed: int) -> tuple[str, str]:
    """Writes scope["canary"] into the clone, confirms it passes pristine on its own
    (a failing canary is this script's bug, not the subject's -- never relied on
    un-verified), runs mutmut for real, and compares the measured killed count against
    `baseline_killed` (the count-match check's own measurement, taken before the canary
    ever existed). Returns (KILLS|NO-KILLS|ERROR, note). Always resets the clone before
    returning, success or failure, so the probe never leaves paid-cell state behind."""
    canary_body = scope.get("canary")
    if not canary_body:
        return "ERROR", "protocol.json subject has no 'canary' field"

    env = _make_env(clone_dir, scope)
    try:
        env.reset_clone()
        env.preflight(scope["module"])
        canary_path = clone_dir / CANARY_REL_PATH
        canary_path.parent.mkdir(parents=True, exist_ok=True)
        canary_path.write_text(canary_body)

        from crucible.runner import run_tests
        pristine = run_tests(clone_dir, test_paths=[str(CANARY_REL_PATH)])
        if not pristine.passed:
            return "ERROR", f"canary failed pristine (this is the canary's bug): {pristine.output[-500:]}"

        outcome = env.measure()
        post_killed = outcome.counts.get("killed", 0)
        delta = post_killed - baseline_killed
        note = f"{baseline_killed}k -> {post_killed}k (delta {delta:+d})"
        return ("KILLS" if delta > 0 else "NO-KILLS"), note
    except Exception as exc:  # noqa: BLE001 -- report, don't abort the sweep
        return "ERROR", f"{type(exc).__name__}: {exc}"
    finally:
        env.reset_clone()


def _print_table(rows: list[tuple[str, ...]], header: tuple[str, ...]) -> None:
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

    rows = []
    canary_rows = []
    for name, scope in scopes.items():
        row, baseline_killed, clone_dir = validate_subject(name, scope, subjects_meta.get(name))
        rows.append(row)
        if baseline_killed is None:
            canary_rows.append((name, "SKIPPED", "count-match check failed; canary not attempted"))
            continue
        verdict, note = run_canary_probe(name, scope, clone_dir, baseline_killed)
        canary_rows.append((name, verdict, note))

    _print_table(rows, ("subject", "expected", "measured", "verdict", "note"))
    print()
    _print_table(canary_rows, ("subject", "canary", "note"))

    # graph-guard old-vs-new record: run the identical canary probe once more, but
    # against the OLD (pre-v6, include-list) pytest_args -- for the record, per
    # PROTOCOL.md §3.2 v6 amendment. This is the evidence that settles the v5
    # amendment's open concern: if OLD shows NO-KILLS and NEW (the table above)
    # shows KILLS, graph-guard's counted H1 cells are proven instrument-invalid,
    # not just suspected.
    if "graph-guard" in scopes:
        old_scope = dict(scopes["graph-guard"])
        old_scope["pytest_args"] = ["tests/test_ppr.py"]
        clone_dir = CRUCIBLE_SUBJECTS / "graph-guard"
        if clone_dir.exists():
            gg_row, gg_baseline, gg_clone = validate_subject("graph-guard", old_scope, subjects_meta.get("graph-guard"))
            print()
            print("graph-guard OLD (pre-v6, include-list pytest_args=['tests/test_ppr.py']) -- for the record:")
            if gg_baseline is None:
                print(f"  count-match under OLD scope failed: {gg_row}")
            else:
                verdict, note = run_canary_probe("graph-guard", old_scope, gg_clone, gg_baseline)
                print(f"  canary under OLD scope: {verdict} ({note})")
            # The OLD-scope probe above commits a throwaway [tool.mutmut] scope into
            # the clone (preflight commits any scope it writes). Restore the clone's
            # HEAD to the real, currently-frozen protocol.json scope before returning,
            # so this script never leaves the shared clone pointed at a stale scope
            # for a later real `crucible experiment` cell.
            real_env = _make_env(clone_dir, scopes["graph-guard"])
            real_env.reset_clone()
            real_env.preflight(scopes["graph-guard"]["module"])

    mismatches = [r for r in rows if r[3] != "MATCH"]
    no_kills = [r for r in canary_rows if r[1] != "KILLS"]
    print()
    ok = True
    if mismatches:
        print(f"{len(mismatches)}/{len(rows)} subject(s) MISMATCH: "
              f"{', '.join(r[0] for r in mismatches)}")
        ok = False
    else:
        print(f"{len(rows)}/{len(rows)} subjects MATCH")
    if no_kills:
        print(f"{len(no_kills)}/{len(canary_rows)} subject(s) canary NOT KILLS: "
              f"{', '.join(r[0] for r in no_kills)}")
        ok = False
    else:
        print(f"{len(canary_rows)}/{len(canary_rows)} subjects canary KILLS")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
