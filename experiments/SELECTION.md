# Third-party subject selection criteria (committed before selection)

Candidates come from the top of the PyPI most-downloaded list (hugovk top-pypi-packages
snapshot current at selection date), scanned IN RANK ORDER. First 2 packages meeting ALL
criteria are selected — no discretion:

1. Pure Python (no C extensions), installable editable from a git clone.
2. Permissive license (MIT/BSD/Apache).
3. Has an existing pytest test suite (which we will strip in the clone).
4. Has at least one module of 100-800 source lines of plain logic (no network/IO-heavy
   modules) — the first qualifying module in alphabetical order becomes the target.
5. mutmut 3 generates >= 40 mutants for that module in a smoke run.
6. Not authored by, contributed to, or previously analyzed by Jeff (no familiarity edge).

Exclusions and the walk order are recorded in subjects.json as selection_log.
