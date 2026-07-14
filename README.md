# crucible

**Your AI wrote the tests. Who tested the tests?**

[![ci](https://github.com/Jott2121/crucible/actions/workflows/ci.yml/badge.svg)](https://github.com/Jott2121/crucible/actions/workflows/ci.yml)
[![codeql](https://github.com/Jott2121/crucible/actions/workflows/codeql.yml/badge.svg)](https://github.com/Jott2121/crucible/actions/workflows/codeql.yml)
[![mutation score](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Jott2121/crucible/badges/mutation.json&labelColor=0F172A)](docs/MUTATION.md)
[![tests](https://img.shields.io/badge/tests-439-38BDF8?labelColor=0F172A)](tests/)
[![loop effect](https://img.shields.io/badge/loop_causal_effect-0.783_%5B0.59%2C0.94%5D-818CF8?labelColor=0F172A)](experiments/RESULTS-B.md)
[![cross-config pilot](https://img.shields.io/badge/cross--config_pilot-%2B0.178_%5B0.04%2C0.35%5D-FBBF24?labelColor=0F172A)](experiments/RESULTS-B.md)
[![metered spend](https://img.shields.io/badge/metered_spend-%240-34D399?labelColor=0F172A)](#receipts-are-the-product)
[![license](https://img.shields.io/badge/license-MIT-64748B?labelColor=0F172A)](LICENSE)

![crucible demo — a green suite at 97% coverage, 25 of 71 injected defects surviving, and the harden loop killing 24 of them while refusing to fake the 25th](docs/assets/demo.gif)

<sub>Recorded live — every command really ran, and every number in it is read back from that run's
own receipt. Sped up for viewing; [replay the raw cast at real speed](docs/assets/demo.cast).
Full landing page: **[jott2121.github.io/crucible](https://jott2121.github.io/crucible/)**</sub>

That module has **7 passing tests and 97% line coverage**. Mutation testing injects **71 real
defects**. The suite kills 46. **25 survive** — twenty-five real bugs walking straight through a
green build.

crucible kills **24 of the 25**, and then does the more important thing: in two rounds the Critic
wrote tests that **failed on pristine code**, and crucible **threw them out** rather than bank a
kill it hadn't earned. The loop ends `dry` with one mutant still standing, and says so. Mutation
score 65% → 99%; **line coverage never moves off 97% the entire time.** Coverage was never the
thing measuring your safety.

An earlier run on the same module killed all 25 (`clean`). Same tool, same module, different day —
model nondeterminism is real, and the receipts record both rather than only the flattering one.

## Put the number in your own PRs

The diagnose costs nothing and calls no model. Point the Action at a module and every pull request
tells you how many real bugs your suite would actually have caught:

```yaml
- uses: Jott2121/crucible@v1
  with:
    module: yourpkg/yourmodule.py    # omit if your repo already configures [tool.mutmut]
    fail-under: "70"                 # optional: red the build below this
```

It comments the score and names the survivors. **No model, no API key, `$0`** — the number that
embarrasses a coverage badge is free to compute, and you should not need a subscription to be told
the truth about your own tests.

For the badge, set `badge-file: mutation.json`, publish it, and point shields.io at it. The payload
lives in **your** repo — there is no badge service of mine sitting in the middle of your CI, and no
uptime I owe you. The badge at the top of this page is generated exactly that way, by this Action,
on this repo:

```markdown
[![mutation](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/YOU/REPO/badges/mutation.json)](...)
```

Or just run it locally, on any repo, right now:

```
crucible score . --module yourpkg/yourmodule.py --coverage 97
97% line coverage, but 25 of 71 injected defects SURVIVED this suite (46 killed, mutation score 65%).
```

Coverage measures what ran, not what would be caught. Mutation testing injects real defects
and counts how many your suite kills — and AI-written suites routinely leave survivors.
crucible closes the loop: a **Tester** agent writes tests, **mutmut** finds the survivors —
injected defects no test caught — and a **Critic** agent is handed the named survivors and
writes tests to kill exactly those. Every verdict is mechanical: pytest kills the mutant or
it survives. **No model ever grades model output.**

## Quickstart — the free first win (no model, no keys, one command)

Find out what your existing tests actually miss, on your own repo:

    pip install "crucible @ git+https://github.com/Jott2121/crucible@v1"

    cd /path/to/your-repo-clone       # work in a clone: crucible writes scope config
    crucible score . --module yourpkg/yourmodule.py --coverage 97

    97% line coverage, but 25 of 71 injected defects SURVIVED this suite (46 killed, mutation score 65%).

**No model is called and no API key is needed.** `crucible score` detects your layout, writes the
mutation scope, and **proves** a fresh test file is collectable before anything else runs (a canary
probe; it refuses — exit 4 — rather than guess). If your repo already configures `[tool.mutmut]`,
drop `--module` and crucible grades the scope you chose instead of overwriting it.

The survivor count is plain mutation testing on your own suite. No AI is involved yet — the number
that embarrasses a coverage badge is free to compute.

## Then harden — the adversarial loop

    crucible harden . --module yourpkg/yourmodule.py \
        --tester claude-cli --critic claude-cli --runs-dir ~/.crucible-runs/yourrepo

With `claude-cli`, model calls run through Claude Code headless on your Claude subscription —
**$0 metered spend**, and every run's `meta.json` records `billing: max-plan` so plan-covered
shadow dollars are never mistaken for an invoice. No subscription? `--tester anthropic` uses the
metered API via `ANTHROPIC_API_KEY`.

Lean invocation is the default: the subprocess runs with `--tools ""`, collapsing Claude
Code's agent loop to a single completion. On the reference run (`rag_guard/guard.py`), that
took the harden from **439,230 to 3,641 input tokens (120.6×), with identical results — the
same 25/25 surviving mutants killed** (receipts `20260712T050833Z` vs `20260712T171312Z`).
Measured on that run's receipts, not a universal constant. `CRUCIBLE_LEAN=0` restores the
ambient invocation.

## Receipts are the product

Every run writes a receipt directory:

    meta.json         # models, billing (api vs max-plan), lean_isolation rung, scope commit
    receipt.jsonl     # one line per round: tokens in/out, cost, kills, survivors, prompt hash
    result.json       # verdict + totals

Generated tests are written into the working tree of wherever you run it — so run it on a
throwaway branch; the bundled `harden-tests` skill (`.claude/skills/harden-tests/`) enforces
the full ritual: **local branch only, never main, PR strictly opt-in**. If the canary can't
prove your scope, crucible refuses instead of spending tokens.

## Results

Two pre-registered experiments (`experiments/PROTOCOL.md`, `experiments/PROTOCOL-B.md`).
**Experiment 1** ran five subjects across three arms (one-shot, same-lineage adversarial loop,
cross-lineage adversarial loop). The loop-arm pipeline outscored one-shot 105 discordant kills to
0 (pooled exact McNemar p = 4.9×10⁻³²) — a pipeline-level replication of the direction
established by MuTAP, AdverTest, and Meta's ACH (`docs/RELATED-WORK.md`); because each arm drew
its own round-0 suite, it is not a causal estimate of the loop, a confound an external
cross-model review of the draft paper caught. **Experiment 2** removed it: one frozen round-0
suite per replicate (5 per subject × 4 subjects), committed before its continuations, all three
arms run from that identical state. Within that design the Critic loop's incremental effect is
causal and large: a mean **78% of the survivors the frozen round-0 left standing were killed by
the critic rounds** (rate 0.783, 95% bootstrap interval [0.592, 0.935]). The cross-provider
critic configuration — pre-registered as a no-verdict pilot — showed a positive within-replicate
difference (rate gap 0.178 [0.039, 0.347]; direction stable under every leave-one-out
sensitivity, magnitude 59% driven by one receipted truncation failure) at 5.5× lower arm cost.
An earlier analysis had shown an apparently overwhelming cross-lineage effect; the autopsy
traced it to silent output truncation deleting one arm's rounds — an instrument artifact, not a
model difference — and the same mechanism recurred three times in Experiment 2, this time
mechanically detected and honestly scored. That autopsy and the fail-closed instrumentation
built from it are the finding. Full tables: [`experiments/RESULTS.md`](experiments/RESULTS.md)
(Experiment 1), [`experiments/RESULTS-B.md`](experiments/RESULTS-B.md) (Experiment 2), and the
paper draft with its complete cross-model review trail in [`paper/`](paper/).

## Why trust this

The claims above are checkable: both experiments were pre-registered before results existed
(Experiment 2's protocol was pushed publicly before its runner was even built), and
inconclusive or corrected results are published at the same prominence as positive ones —
including a manufactured effect the instrument itself produced, autopsied with receipts.
Additionally, the prior art is cited rather than rediscovered (`docs/RELATED-WORK.md`), and the
tool is dogfooded — crucible's own modules run under the same mutation gate, current score
and survivor dispositions in `docs/MUTATION.md`.

## Honest limitations

- Python + pytest repos only; layout heuristics target well-formed projects — a repo the
  canary can't validate is a refusal, not a guess.
- mutmut is pinned exactly (3.6.0): the src-layout shim relies on a mutmut-internal contract.
- The `claude-cli` provider has no mechanical truncation check (the CLI exposes no output
  cap); disclosed in the provider docstring.
- The 120.6× lean result is one module, one apples-to-apples pair of runs. Your ratio will
  differ; your receipts will tell you.

## How it works

    Tester (writes tests) ──> mutmut (injects defects, counts kills)
          ^                        │ named survivors
          └──── Critic (kills exactly those) <──┘   ... until dry or round cap

Built on [oracle-gate](https://github.com/Jott2121/oracle-gate) (survivor triage, provenance,
providers). MIT license.
