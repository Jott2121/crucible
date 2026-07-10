"""The real env behind the loop: subject clone on disk, real mutmut, real providers.

Everything the loop's duck-type promises, wired to the adapters. Retries live here
(the loop treats a raised exception as abort-after-retries).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from crucible.engine import MutmutEngine
from crucible.guardrails import GuardrailViolation, assert_add_only, extract_test_file, test_filename, validate_new_tests
from crucible.loop import RoundReply
from crucible.meter import cost_usd
from crucible.roles import build_critic_prompt, build_tester_prompt
from crucible.runner import run_tests

RETRIES = 3
BACKOFFS = (2, 8)

# Untracked artifacts crucible's own engine leaves in the subject clone; never
# a model escape route, so the add-only check must not trip on them.
ENGINE_ARTIFACTS = ("mutants/", "mutants", "coverage.json", ".mutmut-cache")


class SubjectEnv:
    def __init__(self, subject_dir, tester_provider, tester_model, critic_provider,
                 critic_model, module_path, run=subprocess.run):
        self.subject_dir = Path(subject_dir)
        self.tester_provider, self.tester_model = tester_provider, tester_model
        self.critic_provider, self.critic_model = critic_provider, critic_model
        self.module_path = module_path
        self.run = run
        self.engine = MutmutEngine(self.subject_dir, run=run)
        self._sleep = time.sleep

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
                return RoundReply(text, prompt.prompt_sha256, model, usage)
            except Exception as exc:
                last = exc
                if attempt < RETRIES - 1:
                    self._sleep(BACKOFFS[min(attempt, len(BACKOFFS) - 1)])
        raise RuntimeError(f"model call failed after {RETRIES} attempts: {last}")

    def call_tester(self) -> RoundReply:
        prompt = build_tester_prompt(self.module_path, self._module_source())
        return self._call(self.tester_provider, self.tester_model, prompt)

    def call_critic(self, survivor_diffs) -> RoundReply:
        prompt = build_critic_prompt(self.module_path, self._module_source(), survivor_diffs)
        return self._call(self.critic_provider, self.critic_model, prompt)

    # --- files / guardrails ---
    def write_test_file(self, round_no, arm, content) -> str:
        body = extract_test_file(content) if content.strip().startswith("```") or "```python" in content else content
        rel = Path("tests") / test_filename(round_no, arm)
        (self.subject_dir / rel).write_text(body + "\n")
        try:
            status = self.run(["git", "status", "--porcelain"], cwd=str(self.subject_dir),
                              capture_output=True, text=True).stdout
            status = "\n".join(
                line for line in status.splitlines()
                if not (line[:2] == "??" and line[3:].strip().rstrip("/") in
                        {a.rstrip("/") for a in ENGINE_ARTIFACTS}
                        or line[:2] == "??" and line[3:].strip().startswith("mutants/"))
            )
            assert_add_only(status, [str(rel)] + self._known_generated())
        except GuardrailViolation:
            (self.subject_dir / rel).unlink(missing_ok=True)
            raise
        return str(rel)

    def _known_generated(self):
        tests_dir = self.subject_dir / "tests"
        return [str(Path("tests") / p.name) for p in tests_dir.glob("crucible_*_test.py")]

    def validate(self, test_path) -> None:
        validate_new_tests(self.subject_dir, test_path,
                           lambda cwd, test_paths=None, timeout=300:
                           run_tests(cwd, test_paths=test_paths, timeout=timeout, run=self.run))

    def remove_test_file(self, path) -> None:
        (self.subject_dir / path).unlink(missing_ok=True)

    # --- money / provenance ---
    def cost_usd(self, model, usage) -> float:
        return cost_usd(model, usage)

    def head_sha(self) -> str:
        return self.run(["git", "rev-parse", "HEAD"], cwd=str(self.subject_dir),
                        capture_output=True, text=True).stdout.strip()
