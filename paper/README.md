# Paper

**Adversarial Test-Hardening for AI-Written Code: An Instrument Autopsy and a Pre-Registered Causal Estimate of the Critic Loop**, Jeff Otterson.

| File | What it is |
| --- | --- |
| `crucible.tex` | The manuscript. Single self-contained LaTeX file: no figures, no `.bib`, standard TeX Live packages only. |
| `crucible.pdf` | The manuscript built from `crucible.tex`. |
| `build.sh` | Builds the PDF and the arXiv source archive. |

## Build

```bash
paper/build.sh            # writes paper/build/crucible.pdf and paper/build/crucible-arxiv.tar.gz
```

Needs `pdflatex` (TeX Live: `texlive-latex-recommended`, `texlive-latex-extra`, `texlive-fonts-recommended`, `lmodern`). The archive holds only `crucible.tex`; arXiv compiles it with pdfLaTeX. `paper/build/` is not committed.

## Numbers

Every figure in the paper is recomputed from the committed receipts under `experiments/`. Check the headline values with:

```bash
python scripts/check_receipts.py
```

## History

Earlier drafts, per-section drafts, the cross-model review rounds, and working notes are in [`docs/paper-history/`](../docs/paper-history/). The review that motivated Experiment 2, cited by `experiments/PROTOCOL-B.md` at its old path `paper/gpt-5.6-review-REJECT.txt`, is now at [`docs/paper-history/reviews/gpt-5.6-review-REJECT.txt`](../docs/paper-history/reviews/gpt-5.6-review-REJECT.txt). The protocol is frozen, so its text was not edited.
