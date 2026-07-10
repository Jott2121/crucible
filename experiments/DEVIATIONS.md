# Deviations Log

This file records every departure from `PROTOCOL.md` after it froze: aborted runs that leave a
missing cell, any rerun (with its justification — reruns are never silent), and any other
deviation from the pre-registered design. One row per event, appended in run order, never
edited retroactively. An empty table below this header means no deviations have occurred yet.

| Date (UTC) | Subject | Arm | Event | Reason | Resolution |
|---|---|---|---|---|---|
| 2026-07-10 16:26 | graph-guard | oneshot | Pilot attempt 1 (oneshot cell) crashed at the baseline measure, before any model call; zero tokens spent | `SubjectEnv.preflight` wrote only `source_paths` into the clone's `[tool.mutmut]`, never the frozen `also_copy`/`pytest_args` scope from `experiments/subjects.json` / `.superpowers/sdd/task-3-fix-report.md`; mutmut's sandbox could not import `graph_guard`, so `mutmut run` evaluated nothing and every mutant reported `not checked`, raising `oracle_gate.survivors.UnclassifiedStatus` | PRE-DATA protocol amendment: `experiments/protocol.json` bumped to `protocol_version` 2 with a machine-readable `subjects` map carrying each subject's frozen scope; `crucible.experiment.run_arm` now threads it into `SubjectEnv`/`write_scope`. Crashed run dir `experiments/runs/graph-guard/oneshot-20260710T162658Z/` left untouched as evidence. No data affected; pilot re-run followed under protocol v2 |
