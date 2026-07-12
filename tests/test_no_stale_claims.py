"""Publication invariant: retracted numbers must not appear in any tracked,
outsider-facing file. Exempt = files whose CONTENT is the retraction or the
definition of this sweep; everywhere else a hit is a published falsehood.
Guards the truth pass of spec 2026-07-12-plan3b2 §3 (exemptions amended
2026-07-12 at execution: this test flagged the plan/spec docs that define it,
and would have flagged its own STALE list once tracked)."""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# experiments/            -- the frozen autopsy discusses the retracted number
# docs/RELATED-WORK.md    -- prior-art discussion references it
# docs/superpowers/       -- process specs/plans defining this sweep quote its targets
# this test file          -- the STALE list IS the tokens
EXEMPT = ("experiments/", "docs/RELATED-WORK.md", "docs/superpowers/",
          "tests/test_no_stale_claims.py")
STALE = ["9.5×10⁻⁶⁶", "3.4×10⁻¹⁸",
         "supported with a load-bearing caveat"]


def _tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, check=True).stdout
    return [f for f in out.splitlines()
            if not any(f == e or f.startswith(e) for e in EXEMPT)]


def test_no_retracted_numbers_outside_exempt_paths():
    hits = []
    for rel in _tracked_files():
        p = REPO / rel
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for tok in STALE:
            if tok in text:
                hits.append(f"{rel}: {tok!r}")
    assert not hits, f"retracted claims still published: {hits}"
