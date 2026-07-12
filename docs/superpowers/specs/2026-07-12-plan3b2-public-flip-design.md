# Design: Plan 3b.2+3 — the public flip (+ residual cleanups)

Date: 2026-07-12
Status: approved (design cockpit approved by Jeff 2026-07-12, "Approve" — three ruled calls:
tool-first packaging, diagnose-free-then-harden funnel, rename to `crucible`).
Build model: sonnet implementers / opus reviewers / Fable orchestrator.
Repo: github.com/Jott2121/ai-agentic-code-testing → **github.com/Jott2121/crucible** (rename at flip).

## 1. What this is

Take the repo public as a **top-tier, tool-first repo with zero falsified claims**. The
differentiator is not novelty (H1 is a replication — MuTAP, AdverTest, Meta ACH came first, and
`docs/RELATED-WORK.md` says so); it is evidence discipline: a pre-registered experiment with a
published null (H2) and truncation-artifact autopsy, mutation-kill receipts for every claim, and
the 120.6x lean-invocation result reproduced on a real run.

**Ground truth that shapes everything (measured 2026-07-12):**
- `experiments/RESULTS.md` (frozen) is already honest: H1 SUPPORTED (pooled p = 4.9×10⁻³²,
  b=105/c=0), H2 NOT supported (p = 0.0625) with the 9.5×10⁻⁶⁶ artifact autopsy at equal
  prominence.
- **`README.md` is the liability.** Its results section still claims H2 "supported with a
  load-bearing caveat, pooled p = 9.5×10⁻⁶⁶" — the exact falsified number — and cites the stale
  H1 p (3.4×10⁻¹⁸). Publishing it would falsify the repo's own thesis.
- **The GitHub repo description is fiction**: it advertises "SMART-style + Cosmic Ray,
  property-based testing, robustness checks" — none of which the code does (crucible drives
  mutmut).
- LICENSE (MIT) exists; no `/Users/` path leaks in tracked files; `.superpowers/` (internal
  ledger) is git-ignored and stays private.

**Explicitly out of scope:** PyPI publishing (no package-name fight this cycle; install is
`pip install git+...` / clone); posting launch copy to X/LinkedIn (the blurb is drafted and
Jeff-gated here; posting is its own later action); any change under `experiments/` (frozen —
verified, never edited); new tool features.

## 2. Acceptance test (the definition of done)

1. **Truth:** an independent reviewer confirms every claim in every outsider-facing file
   (README, repo description, topics, launch blurb) traces to `experiments/RESULTS.md`, a named
   receipt, or the code — and that the stale H2/H1 numbers appear nowhere outside
   `experiments/` (where the autopsy legitimately discusses them) and RELATED-WORK.
2. **Outsider win:** a stranger with Python + pytest and NO model access gets real value from
   the README's first command block (`crucible scope` + mutmut baseline = "N injected defects
   your tests never caught") in ~10 minutes; model access (Claude subscription or API key) is
   required only for step 2 (`crucible harden`).
3. **Repo hygiene:** repo-sentinel audit passes (hiring-readiness checklist; fixes applied);
   suite green `-W error`; CI green.
4. **The flip itself is Jeff's action**: rename + `--visibility public` runs only on his
   explicit go, after he has seen the final README and copy. Everything before that stays
   private.

## 3. Step 1 — truth pass (blocks everything else)

- Rewrite README's Results section from the frozen `RESULTS.md`: H1 = supported, framed as a
  **replication** in a new agentic/repo-level/Python setting (pooled exact McNemar
  p = 4.9×10⁻³², b=105, c=0); H2 = **not supported** (p = 0.0625), with the autopsy stated as
  the finding: the previously "significant" 9.5×10⁻⁶⁶ came from silent output truncation
  rejecting same-lineage critic rounds — an instrument artifact, caught and repaired, and the
  reason fail-closed instrumentation is the tool's design center.
- Replace the GitHub description (see §7 for the drafted copy) and set topics.
- Mechanical sweep: grep the tracked tree (outside `experiments/` and `docs/RELATED-WORK.md`,
  where the autopsy and prior-art discussion legitimately reference them) for the stale tokens
  (`9.5×10⁻⁶⁶`, `3.4×10⁻¹⁸`, "supported with a load-bearing caveat") → zero hits after the pass.
- The old README's "Status: private" line and internal spec pointers go; docs links that remain
  must resolve for an outsider.

## 4. Step 2 — item-3 residual cleanups (small, TDD, same branch)

All four from the accepted-residuals ledger; exact current values verified 2026-07-12:

1. **tox.ini `[pytest]` scanning:** `scope.py`'s discovery-config scan reads `pytest.ini
   [pytest]`, `setup.cfg [tool:pytest]`, and `pyproject.toml` — add `("tox.ini", "pytest")` to
   the same configparser loop (fail-closed posture unchanged).
2. **Dogfood scope:** add `src/crucible/scope.py` AND `src/crucible/lean.py` (new, pure — prime
   target) to crucible's own `[tool.mutmut] source_paths`; run the dogfood pass; triage any new
   survivors per MUTATION.md discipline (report both denominators).
3. **`import_hint` threading on the tool path:** `env.py` already consumes
   `scope["import_hint"]` for tester/critic prompts, but only the experiment path supplies it.
   Thread it through `cli.py`'s harden/oneshot path: when the subject is src-layout (per
   `scope.detect`'s `needs_src_shim`), pass the bare-module import hint into `SubjectEnv`'s
   scope dict so generated tests import efficiently. Behavior-level contract; the plan pins the
   exact wiring.
4. **Exact mutmut pin:** `pyproject.toml` currently has `mutmut>=3,<4` with 3.6.0 installed;
   the SRC_SHIM's `MUTANT_UNDER_TEST` handling couples to mutmut 3.6.0 internals (ledgered).
   Pin `mutmut==3.6.0` with a comment naming that coupling as the reason.

## 5. Step 3 — the outsider README (tool-first spine)

Structure (each claim carries its evidence inline):

1. **Hook** (drafted, Jeff voice-gates): *"Your AI wrote the tests. Who tested the tests?"*
   One paragraph: coverage measures what ran, not what would be caught; mutation testing
   injects real defects and counts how many your suite kills; crucible closes the loop —
   a Tester writes tests, mutmut finds what they miss, a Critic is handed the named survivors.
   Every verdict is mechanical (pytest kills the mutant or it survives); no model ever grades
   model output.
2. **Free first win (no model, no keys, $0):** `crucible scope . --module pkg/mod.py` +
   `mutmut run` → "N injected defects your tests never caught." Real value on the reader's own
   repo in ~10 minutes.
3. **Then harden:** `crucible harden . --module pkg/mod.py --tester claude-cli --critic
   claude-cli` — on a Claude subscription this bills $0 metered (receipts carry
   `billing: max-plan` so shadow dollars are never mistaken for an invoice); API-key providers
   work too. Lean invocation is the default: on the reference run
   (`rag_guard/guard.py`), 3,641 input tokens vs 439,230 ambient — **120.6x, measured on that
   run's receipts, not a universal constant** — with identical kills (25/25).
4. **Receipts:** what a run directory contains (meta.json with billing + lean_isolation,
   receipt.jsonl per round, result.json) and why receipts are the product.
5. **Why trust this:** the pre-registered experiment — H1 replicated (with the replication
   framing and RELATED-WORK citations up front), **H2 null published at full prominence** with
   the truncation-artifact autopsy, and the instrument-repair narrative. The point stated
   plainly: this repo's differentiator is that its claims are checkable.
6. **Guardrails & honest limitations:** local-branch-only writes, PR strictly opt-in, canary
   refusal semantics (exit 4), heuristics target well-formed pytest repos, no truncation
   detection on the CLI provider (disclosed), Python-only, mutmut-pinned.
7. **How it works** (Tester → mutmut → Critic diagram in text), install, links
   (RESULTS.md, PROTOCOL.md, RELATED-WORK.md, MUTATION.md — the dogfood receipts).

## 6. Step 4 — repo-sentinel audit

Run the existing repo-sentinel skill on the repo after steps 1–3 land: security/correctness/
README-vs-code drift/legibility checklist; fixes to the working branch; ranked report retained.
Drift checking is load-bearing here — it is the mechanical backstop that the new README matches
the code.

## 7. Step 5 — positioning copy (all Jeff-gated before use)

- **Repo description (draft):** "Adversarial test-hardening for AI-written code: a Tester
  writes tests, mutation testing finds what they miss, a Critic kills the named survivors.
  Mechanical verdicts, mutation-kill receipts, $0 on a Claude subscription."
- **Topics (draft):** `mutation-testing`, `ai-generated-code`, `testing`, `llm`, `agents`,
  `pytest`, `mutmut`, `test-generation`, `claude`.
- **Launch blurb** (~150 words, plain .txt to ~/Desktop per doctrine, for wherever Jeff posts):
  honest headline = the null + the autopsy + the 120x receipt; explicitly "replication of the
  adversarial-loop direction (MuTAP/AdverTest/Meta ACH), new setting"; no invented novelty.
- Naming note: other projects named "crucible" exist; the GitHub namespace `Jott2121/crucible`
  is the identity claimed; PyPI is untouched this cycle.

## 8. Step 6 — the flip (Jeff's button)

Staged commands presented to Jeff, run only on his go, in order: (1) `gh repo rename crucible`
(old URL 301-redirects), (2) description + topics via `gh repo edit`, (3)
`gh repo edit --visibility public`. Post-flip verification: logged-out fetch of the README
renders correctly, CI badge resolves, old URL redirects.

## 9. Testing & review

- Item-3 code changes: TDD; suite green `-W error` at every commit; dogfood mutation pass for
  the scope additions.
- Truth pass + README: no unit tests — instead an **adversarial claims review** (opus): every
  factual sentence in outsider-facing files mapped to its source (RESULTS.md line, receipt
  path, or code); any unsourced claim is a defect.
- repo-sentinel run is itself a check; its findings feed a fix wave.
- Standing rules unchanged: builder never verifies own work; ledger updated per task; no
  paid/Max-billed model call in any test.

## 10. Risks (from the approved cockpit)

- **HIGH — stale-claim leakage:** mitigated by truth-pass-first ordering + the adversarial
  claims review + the mechanical grep sweep (§3).
- **MED — overclaiming the 120x:** always stated as measured-on-the-reference-run with the
  receipt named; never as a constant.
- **LOW — name collision:** GitHub-namespace only this cycle.
- **LOW — code+docs on one branch:** suite green at every commit; item-3 changes are small and
  independently reviewed.

## 11. YAGNI cuts (recorded)

- No PyPI packaging/publishing.
- No docs site, no logo/banner art, no GIF-casts — the receipt blocks ARE the demo.
- No new tool features for launch; no changes to `loop.py`/`guardrails.py`/`experiments/`.
- No auto-posting anywhere; launch blurb is a text file Jeff uses himself.
