# Plan 3b.1 Task 1 — isolation probe results (mechanism-check)

Date: 2026-07-12. CLI: Claude Code 2.1.207. Model: claude-sonnet-5. Billing: max-plan ($0 metered).

## Headline: the spec's premise was wrong; the real lever is ~75x (CONFIRMED)

The spec assumed the ~439,230 input tokens per hardened module was a large per-call **session
preload** dominated by MCP tool schemas, cuttable an order of magnitude by config isolation.
**Measurement falsified that and found a bigger, different lever.**

**CONFIRMED (clean Python harness, `scripts/measure_tester.py`, stdin like the real provider):**

```
baseline (no flags):   num_turns=4   in=119,229   out=10,371   -> valid test, 6911 chars
lean (--tools ""...):  num_turns=1   in=  1,593   out= 6,172   -> valid test, 5207 chars
```

**~75x input reduction (119,229 -> 1,593), still producing a real test file.** `--tools ""` does
TWO things: (1) removes the built-in tool definitions (the ~20k "stable preload" was
Bash/Read/Edit/Write schemas, NOT MCP), and (2) collapses the agent loop from 4 turns to 1. Baseline
~= turns x ~30k; the receipt's 325,834 was simply more turns.

### Correction: the "auth instability" was a measurement artifact, not real

The earlier "Not logged in" failures were NOT an auth/throttle problem. They came from an earlier
BASH harness that interpolated guard.py (a RAG-guard full of backticks/`$`/quotes) through a
double-quoted shell variable, corrupting the payload; `claude` rejected the garbage with a
misleading "Not logged in". The Python harness (subprocess stdin, no shell -- exactly how the
provider calls) succeeds every time. **The "provider needs auth retry-with-backoff" requirement is
RETRACTED** -- there was no real instability. Lesson: measure the way the code actually calls.

## What the numbers actually show

### Per-call preload is ~30k, not ~439k

Raw usage for a trivial `claude -p` call (`--system-prompt "probe"`, user "Reply OK"):

```
input_tokens=2  cache_creation_input_tokens=9,991  cache_read_input_tokens=20,003  => SUM_in ~30,006
```

~20k is the stable cached preload (base system prompt + built-in tool defs), ~10k is the per-session
cache write. guard.py is only ~600 tokens (57 lines); this repo and rag-guard have **no CLAUDE.md**,
so cwd/project context adds nothing.

### The isolation-flag ladder (trivial-call input tokens, all auth OK)

| rung | flags | input_tokens | cut vs baseline |
|------|-------|--------------|-----------------|
| 0 baseline | (none) | 30,010 | — |
| 1 strict-mcp | `--strict-mcp-config` | 29,798 | **212 tokens (0.7%)** |
| 2 no-settings | `--strict-mcp-config --setting-sources ""` | 23,328 | **~22%** |
| 3 proj-only+cwd | `--setting-sources project` + neutral cwd | 23,328 | ~22% |
| 4 none+cwd | rung 2 + neutral cwd | 23,328 | ~22% |
| 5 isolated-cfg | rung 4 + `CLAUDE_CONFIG_DIR=<empty>` | ERR (non-auth) | — |

**MCP is NOT the bulk** — `--strict-mcp-config` saved 212 tokens. **`--setting-sources ""`**
(drops skills, CLAUDE.md, plugins, hooks; auth handled separately, unaffected) is the only real
config lever, and it caps out at **~22%** — nowhere near an order of magnitude. Neutral cwd adds
nothing here. `CLAUDE_CONFIG_DIR` isolation errored and is dropped (YAGNI + auth risk).

### The real 439k = 2 calls, and the driver is num_turns, not preload

Baseline receipt `20260712T050833Z-rag-guard-harden/receipt.jsonl`:

```
round 0 tester in=325,834 out=15,677 kills=23
round 1 critic in=113,396 out= 4,856 kills=2
TOTAL       in=439,230 out=20,533
```

A single tester call is 325,834 input — ~11x the ~30k trivial preload — on a 600-token module. The
coherent explanation: **`claude -p` is an agent, not a one-shot completion.** A real generation task
runs multiple internal turns (think / tool-consider / generate), and each turn re-reads the ~30k
cached preload as `cache_read`. ~11 turns x ~30k ≈ 325k. The trivial call is num_turns=1 = ~30k.

### The real lever: `--tools ""` (collapse the agent turn loop)

CLI 2.1.207 exposes `--tools ""` ("disable all tools"). With no tools, the tester/critic prompt (which
only needs text out) should collapse to a single completion — num_turns 1, input ~23-30k instead of
~325k. That is where an order of magnitude lives; **config isolation is a secondary ~22% on top.**
Combined single-turn + `--setting-sources ""` projects a tester call at ~23k vs 325,834 (~14x).

**Status: CONFIRMED** (see the headline; `--tools ""` collapses num_turns 4->1 and input 119,229->1,593).

## Decisions recorded

- **`--tools ""` is the primary lever:** removes built-in tool schemas AND collapses the agent turn
  loop. ~75x on the tester call. This is the design, not config isolation.
- **`--setting-sources ""`** (+ harmless `--strict-mcp-config`) is a minor add-on; with `--tools ""`
  already collapsing the preload to ~1.6k, its ~22% is largely subsumed. Keep both (cheap, no risk).
- **DROP** `CLAUDE_CONFIG_DIR` isolation (rung 5): errored, auth-risky, and completely unnecessary —
  the win is entirely in `--tools ""`.
- **RETRACTED:** the "auth instability / provider needs retry" requirement — it was a bash-harness
  artifact, not real (see correction above).
- **OPEN (Task 6 proof):** the token win is proven; the remaining question is EFFICACY — does the
  single-turn, tool-less tester still KILL mutants as well as the multi-turn baseline? crucible's
  mutation loop is the external verifier, so the model does not need self-verification tools, but the
  full harden re-run on guard.py must confirm the 25 baseline survivors still die under lean.
