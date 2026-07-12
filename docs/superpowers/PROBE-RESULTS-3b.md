# Plan 3b.1 Task 1 — isolation probe results (mechanism-check)

Date: 2026-07-12. CLI: Claude Code 2.1.207. Model: claude-sonnet-5. Billing: max-plan ($0 metered).

## Headline: the spec's premise was wrong (this is why we probe first)

The spec assumed the ~439,230 input tokens per hardened module was a large per-call **session
preload** dominated by MCP tool schemas, cuttable an order of magnitude by config isolation.
**Measurement falsified all three claims.**

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

**Status: STRONGLY INFERRED, NOT YET CONFIRMED LIVE** — see the blocker below.

## Blocker discovered: auth/throttle instability under load

After ~12-14 rapid `claude -p` calls, every **tester-payload** call began returning
`is_error=true, result="Not logged in · Please run /login"` in ~41ms (pre-flight reject), while
**trivial** calls interleaved successfully (29,991 tokens, is_error=false). So it is not a hard
logout — it is a heavy/rapid-call throttle surfacing as an auth error. This blocked live
confirmation of the `--tools ""` collapse.

**This is itself a first-class finding:** the harden loop fires sequential heavy `claude -p` calls,
and the current provider has **no retry** — it fails loud on the first error. A real run can hit this
(the gate-7 run happened to succeed). Retry-with-backoff on transient/auth-class errors belongs in
the design regardless.

## Decisions recorded

- **DROP** `CLAUDE_CONFIG_DIR` isolation (rung 5): errored, auth-risky, unnecessary — the win is not
  there. The spec's "go for the floor via config isolation" is retired by evidence.
- **NEW primary lever:** `--tools ""` to collapse num_turns (pending one live confirmation).
- **Secondary lever:** `--setting-sources ""` (+ harmless `--strict-mcp-config`) for ~22%/turn.
- **New requirement:** transient/auth-class retry-with-backoff in the provider.
- **NEXT (needs fresh auth):** one clean tester-payload call with `--tools "" --setting-sources "" --strict-mcp-config`
  measuring num_turns + summed input, vs the 325,834 baseline. Confirm the collapse before finalizing
  the revised spec.
