"""The real env behind the loop: subject clone on disk, real mutmut, real providers.

Everything the loop's duck-type promises, wired to the adapters. Retries live here
(the loop treats a raised exception as abort-after-retries).
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from crucible.engine import MutmutEngine, write_scope
from crucible.guardrails import (
    GuardrailViolation,
    assert_add_only,
    extract_test_file,
    salvage_new_tests,
    test_filename,
)
from crucible.loop import RoundReply
from crucible.meter import cost_usd
from crucible.providers_ext import TruncatedOutput
from crucible.roles import build_critic_prompt, build_tester_prompt
from crucible.runner import run_tests

RETRIES = 3
BACKOFFS = (2, 8)

# Untracked artifacts crucible's own engine leaves in the subject clone; never
# a model escape route, so the add-only check must not trip on them.
ENGINE_ARTIFACTS = ("mutants/", "mutants", "coverage.json", ".mutmut-cache")


class SubjectEnv:
    def __init__(self, subject_dir, tester_provider, tester_model, critic_provider,
                 critic_model, module_path, run=subprocess.run, scope: dict | None = None):
        self.subject_dir = Path(subject_dir)
        self.tester_provider, self.tester_model = tester_provider, tester_model
        self.critic_provider, self.critic_model = critic_provider, critic_model
        self.module_path = module_path
        self.run = run
        self.scope = scope
        self.engine = MutmutEngine(self.subject_dir, run=run)
        self._sleep = time.sleep
        # set by run_arm via set_artifact_dir(run_dir); None = no preservation (unit
        # tests, and any caller that hasn't opted in keep today's unlink/delete behavior)
        self._artifact_dir: Path | None = None

    # --- git (fail loud: a swallowed git error corrupts provenance) ---
    def _git(self, *args) -> str:
        proc = self.run(["git", *args], cwd=str(self.subject_dir),
                        capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed in {self.subject_dir}: "
                               f"{(proc.stderr or '').strip()}")
        return proc.stdout

    def _filtered_status(self) -> str:
        """git status --porcelain -uall minus crucible's own engine artifacts.

        -uall (vs. porcelain's default -unormal) makes untracked directories
        enumerate their contents as individual `?? tests/foo_test.py` lines
        instead of collapsing to a single `?? tests/` line. A stripped subject
        has no tracked `tests/` dir, so the first generated test file makes it
        untracked-new; without -uall the collapsed line never matches the
        add-only allowlist (which lists file paths), and a legitimately
        written file gets rejected as tampering. The two-char status codes and
        everything else about the output are unchanged."""
        status = self._git("status", "--porcelain", "-uall")
        return "\n".join(
            line for line in status.splitlines()
            if not (line[:2] == "??" and line[3:].strip().rstrip("/") in
                    {a.rstrip("/") for a in ENGINE_ARTIFACTS}
                    or line[:2] == "??" and line[3:].strip().startswith("mutants/"))
        )

    def reset_clone(self) -> None:
        """Cell isolation: restore the clone to its committed state. Removes prior
        cells' generated tests and engine caches; tracked files reset to HEAD."""
        self._git("checkout", "--", ".")
        for p in (self.subject_dir / "tests").glob("crucible_*_test.py"):
            p.unlink()
        shutil.rmtree(self.subject_dir / "mutants", ignore_errors=True)

    def preflight(self, module_path: str | None = None) -> str:
        """Hard stop before any model is called: the clone must be a git work tree,
        clean, and green on pristine code. If module_path is given, [tool.mutmut]
        scope is written and committed inside the clone, so the returned HEAD sha
        (which receipts bind to) includes the scope. ScopeError (no pyproject.toml)
        propagates — also a hard stop."""
        self._git("rev-parse", "--is-inside-work-tree")
        if self._filtered_status().strip():
            raise RuntimeError(
                "subject clone is dirty; commit or clean it (receipts must bind to a commit)"
            )
        if module_path:
            # v7: import shims (e.g. a src-layout conftest.py that puts src/ on
            # sys.path) are written BEFORE the scope-change commit below, so the
            # same commit captures both — a receipt's head_sha then covers the
            # shim too, not just the [tool.mutmut] table. Written only when
            # content actually differs, so a no-op preflight (scope already
            # written, shim already committed identically) stays a true no-op.
            extra_files = (self.scope or {}).get("extra_files") or {}
            for rel_path, content in extra_files.items():
                target = self.subject_dir / rel_path
                if not target.exists() or target.read_text() != content:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content)
            if self.scope is not None:
                write_scope(self.subject_dir / "pyproject.toml", [module_path],
                           also_copy=self.scope.get("also_copy"),
                           pytest_args=self.scope.get("pytest_args"),
                           create_if_missing=True)
            else:
                write_scope(self.subject_dir / "pyproject.toml", [module_path],
                           create_if_missing=True)
            if self._git("status", "--porcelain", "-uall").strip():
                self._git("add", "pyproject.toml", *extra_files.keys())
                commit_msg = f"crucible: scope mutmut to {module_path}"
                if extra_files:
                    commit_msg += " (+shims)"
                self._git("-c", "user.email=crucible@local", "-c", "user.name=crucible",
                          "commit", "-qm", commit_msg)
        pristine = run_tests(self.subject_dir, run=self.run)
        # pytest exit 5 = "no tests collected": a stripped subject is a valid
        # pristine state (crucible's job is to create the tests). Anything else
        # non-zero is a red suite: hard stop before any model is called.
        if not pristine.passed and pristine.returncode != 5:
            raise RuntimeError(
                "subject suite is red on pristine code; hard stop before any model "
                f"is called\n{pristine.output[-2000:]}"
            )
        return self.head_sha()

    # --- mutation ---
    def measure(self):
        return self.engine.measure()

    def survivor_diff(self, mid):
        return self.engine.survivor_diff(mid)

    # --- models ---
    def _module_source(self) -> str:
        return (self.subject_dir / self.module_path).read_text()

    def _call(self, provider, model, prompt) -> RoundReply:
        last = None
        for attempt in range(RETRIES):
            try:
                text, usage = provider.complete_with_usage(prompt.system, prompt.user, model=model)
            except Exception as exc:
                last = exc
                if attempt < RETRIES - 1:
                    self._sleep(BACKOFFS[min(attempt, len(BACKOFFS) - 1)])
                continue
            # a mechanical cap hit is billed already; retrying would bill it again
            # and likely truncate again, so it escapes immediately, uncounted
            # against RETRIES and never wrapped in the generic failure below.
            cap = getattr(provider, "output_cap", None)
            if cap is not None and usage.output_tokens >= cap:
                raise TruncatedOutput(text, usage, model, prompt.prompt_sha256, cap)
            return RoundReply(text, prompt.prompt_sha256, model, usage)
        raise RuntimeError(f"model call failed after {RETRIES} attempts: {last}")

    def call_tester(self) -> RoundReply:
        import_hint = (self.scope or {}).get("import_hint")
        prompt = build_tester_prompt(self.module_path, self._module_source(), import_hint=import_hint)
        return self._call(self.tester_provider, self.tester_model, prompt)

    def call_critic(self, survivor_diffs) -> RoundReply:
        import_hint = (self.scope or {}).get("import_hint")
        prompt = build_critic_prompt(self.module_path, self._module_source(), survivor_diffs,
                                     import_hint=import_hint)
        return self._call(self.critic_provider, self.critic_model, prompt)

    # --- files / guardrails ---
    def write_test_file(self, round_no, arm, content) -> str:
        body = extract_test_file(content) if content.strip().startswith("```") or "```python" in content else content
        rel = Path("tests") / test_filename(round_no, arm)
        # a stripped subject (tests/ removed by git rm) has no tests dir at all;
        # create the parent before writing so this doesn't crash FileNotFoundError
        (self.subject_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.subject_dir / rel).write_text(body + "\n")
        try:
            assert_add_only(self._filtered_status(), [str(rel)] + self._known_generated())
        except GuardrailViolation:
            (self.subject_dir / rel).unlink(missing_ok=True)
            raise
        return str(rel)

    def _known_generated(self):
        tests_dir = self.subject_dir / "tests"
        return [str(Path("tests") / p.name) for p in tests_dir.glob("crucible_*_test.py")]

    def set_artifact_dir(self, run_dir) -> None:
        """Opt in to rejected-artifact preservation: called by run_arm with the run's
        receipt directory right after the writer is created. Without this, a rejected
        or salvaged-away test file is unlinked/discarded as before (unit tests, and any
        caller that never opts in)."""
        self._artifact_dir = Path(run_dir)

    def _read_test_file_text(self, cwd, path) -> str:
        return (Path(cwd) / path).read_text()

    def _write_test_file_text(self, cwd, path, content) -> None:
        (Path(cwd) / path).write_text(content)

    def validate(self, test_path) -> list[str]:
        """Per-test salvage (v3): pristine-failing tests are dropped, not the whole
        file. Returns the names dropped (possibly empty). When an artifact dir is set,
        the pre-salvage original is preserved to <artifact_dir>/salvaged/<name>.orig
        before pruning, so a dropped test is data (wrong-oracle evidence), not lost."""
        original = None
        if self._artifact_dir is not None:
            original = (self.subject_dir / test_path).read_text()
        dropped = salvage_new_tests(
            self.subject_dir, test_path,
            lambda cwd, test_paths=None, timeout=300:
                run_tests(cwd, test_paths=test_paths, timeout=timeout, run=self.run),
            self._read_test_file_text, self._write_test_file_text,
        )
        if dropped and self._artifact_dir is not None:
            salvaged_dir = self._artifact_dir / "salvaged"
            salvaged_dir.mkdir(parents=True, exist_ok=True)
            (salvaged_dir / f"{Path(test_path).name}.orig").write_text(original)
        return dropped

    def remove_test_file(self, path, label="rejected") -> None:
        """A rejected round leaves no trace in the subject clone. When an artifact dir
        is set (run_arm's real runs), the file is preserved there instead of deleted —
        a rejected test is interesting data (spec: never counted as a kill, but never
        thrown away either), not just discarded."""
        full = self.subject_dir / path
        if self._artifact_dir is not None:
            rejected_dir = self._artifact_dir / "rejected"
            rejected_dir.mkdir(parents=True, exist_ok=True)
            if full.exists():
                full.replace(rejected_dir / f"{label}-{Path(path).name}")
            return
        full.unlink(missing_ok=True)

    def archive_rejected_text(self, round_no, arm, text, label="truncated") -> None:
        """A truncated (or otherwise text-only rejected) model reply is evidence,
        never silently discarded -- mirrors remove_test_file's preservation, but
        for a reply that was never written to the subject clone at all (there is
        no test file to move). No-op when no artifact dir is set (unit tests)."""
        if self._artifact_dir is None:
            return
        rejected_dir = self._artifact_dir / "rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        (rejected_dir / f"{label}-r{round_no}-{arm}.txt").write_text(text)

    def assert_clean(self, allowed_new=None) -> None:
        """Post-round integrity attestation: after tests execute, the tree must show
        nothing but crucible's own generated test files (engine artifacts filtered).
        Any other line — including a MODIFIED tracked file — is tampering."""
        allowed = self._known_generated() if allowed_new is None else allowed_new
        assert_add_only(self._filtered_status(), allowed)

    # --- money / provenance ---
    def cost_usd(self, model, usage) -> float:
        return cost_usd(model, usage)

    def head_sha(self) -> str:
        return self._git("rev-parse", "HEAD").strip()
