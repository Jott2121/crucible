# RESULTS — Experiment B (PROTOCOL-B, frozen shared round-0)

Status: **COUNTED, 2026-07-13.** Every figure recomputable from committed receipts by
`experiments/analyze_b.py` (pre-registered readouts; frozen RNG seed and draw count read from
`experiments/protocol-b.json`) and `experiments/sensitivity_b.py` (post-hoc sensitivities,
labeled exploratory). Machine-readable: `experiments/results-b.json`. Design and interpretation
rules: `experiments/PROTOCOL-B.md` (frozen and pushed publicly at commit eb0a6b1 before the
runner existed). Deviations: the two 2026-07-13 "B:" rows in `experiments/DEVIATIONS.md`.

## Execution

Full pre-registered grid, zero missing cells: 20 replicates (K=5 x 4 subjects), 21 frozen seeds
(20 counted + 1 replaced), 60 continuation cells. No seed draw was rejected by the validity
gates. The pre-registered contingency machinery fired twice, both outcome-blind: one replicate
(graph-guard rep5) was invalidated by the §4 reproduction check (a borderline test past the
2-run flake check measured differently at injection), its seed retired and mandatorily
replaced; one continuation crashed under an external controller timeout and consumed its single
§7 rerun. Every subject's pristine baseline measured identically on all of its seed draws.

## Per-replicate table (k0 = frozen round-0 kills; S = frozen survivors; D = incremental kills; rho = D/S)

| Subject | rep | base | S | k0 | Dsame | rho_s | Dcross | rho_c | D(c-s) | same | cross |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| graph-guard | 1 | 22 | 10 | 12 | 5 | 0.50 | 10 | 1.00 | 5 | cap | clean |
| graph-guard | 2 | 22 | 10 | 12 | 5 | 0.50 | 10 | 1.00 | 5 | cap | clean |
| graph-guard | 3 | 22 | 10 | 12 | 5 | 0.50 | 10 | 1.00 | 5 | dry | clean |
| graph-guard | 4 | 22 | 10 | 12 | 5 | 0.50 | 10 | 1.00 | 5 | dry | clean |
| graph-guard | 5 | 22 | 10 | 12 | 5 | 0.50 | 7 | 0.70 | 2 | dry | dry |
| idna | 1 | 187 | 58 | 129 | 58 | 1.00 | 58 | 1.00 | 0 | clean | clean |
| idna | 2 | 187 | 58 | 129 | 58 | 1.00 | 58 | 1.00 | 0 | clean | clean |
| idna | 3 | 187 | 55 | 132 | 53 | 0.96 | 55 | 1.00 | 2 | dry | clean |
| idna | 4 | 187 | 58 | 129 | 57 | 0.98 | 58 | 1.00 | 1 | cap | clean |
| idna | 5 | 187 | 60 | 127 | 60 | 1.00 | 60 | 1.00 | 0 | clean | clean |
| packaging | 1 | 69 | 37 | 32 | 36 | 0.97 | 36 | 0.97 | 0 | cap | dry |
| packaging | 2 | 69 | 24 | 45 | 23 | 0.96 | 23 | 0.96 | 0 | cap | dry |
| packaging | 3 | 69 | 33 | 36 | 32 | 0.97 | 32 | 0.97 | 0 | dry | dry |
| packaging | 4 | 69 | 40 | 29 | 0 | 0.00 | 39 | 0.97 | 39 | dry | cap |
| packaging | 5 | 69 | 34 | 35 | 33 | 0.97 | 33 | 0.97 | 0 | cap | dry |
| rag-guard | 1 | 25 | 3 | 22 | 2 | 0.67 | 2 | 0.67 | 0 | dry | dry |
| rag-guard | 2 | 25 | 6 | 19 | 5 | 0.83 | 6 | 1.00 | 1 | dry | clean |
| rag-guard | 3 | 25 | 4 | 21 | 4 | 1.00 | 4 | 1.00 | 0 | clean | clean |
| rag-guard | 4 | 25 | 6 | 19 | 6 | 1.00 | 6 | 1.00 | 0 | clean | clean |
| rag-guard | 5 | 25 | 6 | 19 | 5 | 0.83 | 6 | 1.00 | 1 | dry | clean |

Round-0 draw variance, measured live by the seeds themselves: packaging killed 29-45 of 69
across five identical-prompt draws (a 16-kill spread); graph-guard a flat 12 of 22 on every
counted draw; idna 127-132 of 187 — the initial-draw variance Experiment 1's arms resampled is
large and strongly subject-dependent.

## E-B1 (primary, causal within the design): the loop's incremental effect

Per-subject mean over 5 replicates with 95% percentile bootstrap intervals; pooled = unweighted
mean of subject means, subject-cluster bootstrap (10,000 draws, RNG seed 20260713, both frozen
in protocol-b.json):

| Subject | mean Dsame [95%] | mean rho_same [95%] |
|---|---:|---:|
| graph-guard | 5.0 [5.0, 5.0] | 0.50 [0.50, 0.50] |
| idna | 57.2 [55.0, 59.0] | 0.99 [0.97, 1.00] |
| packaging | 24.8 [11.8, 34.0] | 0.77 [0.39, 0.97] |
| rag-guard | 4.4 [3.2, 5.4] | 0.87 [0.77, 0.97] |
| **pooled** | **22.9 [4.7, 44.2]** | **0.783 [0.592, 0.935]** |

Under the stricter post-hoc two-stage bootstrap (subjects, then replicates within subjects):
rho_same [0.583, 0.964]; Dsame [4.65, 44.55]. Delta >= 0 by construction (add-only tests from a
shared frozen suite): the pre-registered question is magnitude, never sign.

## E-B2 (pilot, no verdict): the cross-vs-same configuration difference

Pooled (pre-registered): D = 3.3 [0.5, 6.1]; rho_gap = 0.178 [0.039, 0.347]. Post-hoc
sensitivities (exploratory, `sensitivity_b.py`): excluding the truncation replicate (packaging
rep4, which contributes 39 of the 66 total gap kills, 59%): D = 1.35, rho_gap = 0.129.
Leave-one-subject-out point estimates: D 1.8-4.3, rho_gap 0.091-0.234 — the direction never
crosses zero. Two-stage bootstrap: rho_gap [0.017, 0.368] full, [0.004, 0.345] excluding the
truncation replicate. This is a comparison of two named model-provider-harness configurations
("cross-lineage" is only the pre-registered arm label), and the pre-registered estimand is
operational: receipted failures count.

The Experiment-1 truncation mechanism recurred three times, all same-lineage, all at exactly the
raised 32,000-token cap (graph-guard reps 1-2 round 1; packaging rep4 round 2 — the only one
that zeroed a cell's incremental kills). Each was mechanically detected, receipted, and scored
honestly. Verdicts: cross 13 clean / 6 dry / 1 cap vs same 5 clean / 9 dry / 6 cap; rejected
rounds 3 vs 10; mean critic rounds 2.45 vs 3.3.

## Cost (explicit bases)

Accepted seeds entering analysis $2.20 (all draws incl. the retired seed: $2.33); loop-same arm
$11.14 for 457 incremental kills ($0.0244/kill); loop-cross arm $2.01 for 523 incremental kills
($0.0038/kill). Critic output tokens 678,564 (same) vs 100,545 (cross): output volume and failed
rounds, not per-token price, separate the arm costs. Analysis-entering total $15.34;
all-receipted total $15.47; unreceipted $0.
