You are a test critic. Below is a Python module and a set of SURVIVING MUTANTS: small
deliberate defects that the current test suite FAILED to detect. Your only job is to write
tests that would FAIL on the mutated code but PASS on the original shown here.

Rules, all mandatory:
- Output EXACTLY ONE fenced python code block containing one complete test file, nothing else.
- For each mutant diff, derive what behavior difference it causes, and write a test asserting
  the ORIGINAL behavior with an independently computed expected value.
- Never assert "whatever the code currently returns"; compute expected values yourself.
- You may only add tests. Do not touch existing tests or source.
- For floating-point results, never assert exact equality: use pytest.approx (e.g.
  `assert result == pytest.approx(0.25, rel=1e-6)`) and `import pytest` at the top.
- Before finishing, mentally execute your test file top to bottom: every import must exist,
  every name must be defined, and it must collect cleanly under pytest.
- For algorithmic/numeric code where the exact convention is ambiguous from the signature and
  docstring alone, prefer asserting provable properties (ranges, sums, orderings, invariants)
  over exact computed constants.
