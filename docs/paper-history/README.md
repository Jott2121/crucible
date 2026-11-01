# Paper history

How the paper in [`paper/`](../../paper/) got written. Nothing here is part of the manuscript; it is kept so the drafting and review trail stays public and checkable. The final text is `paper/crucible.tex`.

The reviews below are reviews by AI models (OpenAI's GPT-5.6 and a separate Claude instance), run by the author as an outside-the-family check on each draft. They are not journal or conference peer review, and words like ACCEPT or MINOR REVISION in their file names are those models' verdicts on a draft, not a publication decision.

## `drafts/`

Whole-manuscript drafts, oldest first.

| File | Note |
| --- | --- |
| `DRAFT-v1-camera-ready.md` | One-experiment version, before Experiment 2. |
| `DRAFT-v2-two-experiments.md` … `DRAFT-v5-two-experiments.md` | Two-experiment revisions answering the review rounds. |
| `DRAFT-v6-two-experiments.md` | Last Markdown draft; the source of `paper/crucible.tex`. |
| `crucible-paper-v1.pdf` | PDF of v1, which sat in `paper/` as `crucible-paper.pdf` until the cleanup. |
| `crucible-paper-v6.pdf` | PDF of v6 built by pandoc, superseded by `paper/crucible.pdf`. |

## `sections/`

Per-section drafts written and approved one at a time before they were assembled into v1.

## `reviews/`

| File | Draft reviewed | Verdict |
| --- | --- | --- |
| `gpt-5.6-review-REJECT.txt` | v1 | Reject: each arm resampled its own round 0. Motivated Experiment 2 and is cited by `experiments/PROTOCOL-B.md` under its old path `paper/gpt-5.6-review-REJECT.txt`. |
| `gpt-5.6-sol-review-v2-MAJOR-REVISION.txt` | v2 | Major revision |
| `gpt-5.6-sol-review-v3-MAJOR-REVISION.txt` | v3 | Major revision |
| `gpt-5.6-sol-review-v4-MINOR-REVISION.txt` | v4 | Minor revision |
| `gpt-5.6-sol-review-v4-final-ACCEPT.txt` | v4 | Accept, after the minor fixes |
| `fable-postlock-read-v4.txt` | v4 and v5 | Independent recompute of the statistics and a verify pass |
| `gpt-5.6-sol-review-v6-editorial-ACCEPT.txt` | v6 | Editorial confirmation |

## `notes/`

| File | What it is |
| --- | --- |
| `b-minimal-plan.json` | The plan for Experiment 2 (frozen round 0), written after the v1 review. |
| `references-verified.md` | The bibliography check done while drafting Related Work. |
