#!/usr/bin/env python3
"""Prepare crucible subjects: clone each pinned subject into ~/crucible-subjects/<name>,
checkout its pinned SHA, strip tests for third-party subjects, install into this repo's
venv, and smoke-test with pytest. Subject repos are READ-ONLY sources -- all mutation
happens in the clone under ~/crucible-subjects, never in the original repo.

Usage: .venv/bin/python experiments/prep.py [--only NAME]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBJECTS_JSON = REPO_ROOT / "experiments" / "subjects.json"
VENV_PIP = REPO_ROOT / ".venv" / "bin" / "pip"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
CRUCIBLE_SUBJECTS = Path.home() / "crucible-subjects"
GIT_IDENTITY = ["-c", "user.email=crucible@local", "-c", "user.name=crucible"]


def run(cmd, cwd=None, check=True):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(map(str, cmd))}\n{proc.stdout}\n{proc.stderr}")
    return proc


def source_url(subject):
    if subject["source"] == "pypi-git":
        return subject["repo_url"]
    # local:~/attrition-risk-ml -> ~/attrition-risk-ml -> expanded absolute path
    return str(Path(subject["source"].removeprefix("local:")).expanduser())


def extra_groups(pyproject_path):
    """All [project.optional-dependencies] group names, so `pip install -e .[all,groups]`
    pulls in whatever a subject's own test suite needs (e.g. graph-guard's rdf/dev extras)."""
    if not pyproject_path.exists():
        return []
    text = pyproject_path.read_text()
    match = re.search(r"^\[project\.optional-dependencies\]\n((?:(?!^\[).)*)", text, re.M | re.S)
    if not match:
        return []
    return re.findall(r"^(\w[\w-]*)\s*=", match.group(1), re.M)


def find_test_dir(clone_dir):
    for name in ("tests", "test"):
        if (clone_dir / name).is_dir():
            return name
    return None


_TESTPATHS_LINE = re.compile(r'^testpaths\s*=\s*\[[^\]]*\]\s*\n', re.M)


def drop_stale_testpaths(clone_dir, test_dir):
    """Stripping a subject's test suite (git rm -rq test_dir) can leave a
    dangling `testpaths = ["<test_dir>"]` in the subject's own [tool.pytest.
    ini_options]. pytest then warns "No files were found in testpaths" at
    config time; a subject whose OWN config also sets
    filterwarnings=["error"] (e.g. packaging) escalates that warning into a
    hard collection-time crash instead of the honest "no tests collected"
    (exit 5) `SubjectEnv.preflight` expects from a stripped subject -- unlike
    this script's own smoke check below, `crucible.runner.run_tests` (what
    the real experiment's preflight calls) does not carry a `-W ignore`
    workaround, so a stale testpaths line here becomes a hard-stop before any
    model is ever called. Only remove a line that names exactly the
    directory this strip just deleted, so this never touches an unrelated
    testpaths entry (e.g. one still pointing at a docs/ or examples/ test
    dir this strip did not remove).
    """
    pyproject = clone_dir / "pyproject.toml"
    if not pyproject.exists():
        return
    text = pyproject.read_text()
    match = _TESTPATHS_LINE.search(text)
    if not match or f'"{test_dir}"' not in match.group(0):
        return
    pyproject.write_text(_TESTPATHS_LINE.sub("", text, count=1))
    run(["git", *GIT_IDENTITY, "add", "pyproject.toml"], cwd=clone_dir)
    run(["git", *GIT_IDENTITY, "commit", "-q", "-m", "crucible: drop stale testpaths after strip"],
        cwd=clone_dir)


def prepare(subject):
    name = subject["name"]
    clone_dir = CRUCIBLE_SUBJECTS / name
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    CRUCIBLE_SUBJECTS.mkdir(parents=True, exist_ok=True)

    run(["git", "clone", "--quiet", source_url(subject), str(clone_dir)])
    run(["git", "checkout", "--quiet", subject["pinned_sha"]], cwd=clone_dir)

    if subject.get("strip_tests"):
        test_dir = find_test_dir(clone_dir)
        if test_dir:
            run(["git", *GIT_IDENTITY, "rm", "-rq", test_dir], cwd=clone_dir)
            run(["git", *GIT_IDENTITY, "commit", "-q", "-m", "crucible: strip test suite"], cwd=clone_dir)
            drop_stale_testpaths(clone_dir, test_dir)

    has_pkg_metadata = any((clone_dir / f).exists() for f in ("pyproject.toml", "setup.py", "setup.cfg"))
    if has_pkg_metadata:
        extras = extra_groups(clone_dir / "pyproject.toml")
        target = f"{clone_dir}[{','.join(extras)}]" if extras else str(clone_dir)
        run([str(VENV_PIP), "install", "-q", "-e", target])
    else:
        reqs = clone_dir / "requirements.txt"
        if reqs.exists():
            run([str(VENV_PIP), "install", "-q", "-r", str(reqs)])

    pytest_cmd = [str(VENV_PYTHON), "-m", "pytest", "-q"]
    if subject.get("strip_tests"):
        # Stripping the suite leaves a dangling `testpaths` in the subject's own pytest
        # config; pytest warns "No files were found in testpaths" at config time, and a
        # subject with filterwarnings=["error"] (e.g. packaging) escalates that warning
        # into a hard crash. The warning is a direct, expected artifact of the deliberate
        # strip, so silence exactly that warning for stripped subjects only (CLI -W
        # outranks ini filterwarnings in pytest).
        pytest_cmd += ["-W", "ignore::pytest.PytestConfigWarning"]
    smoke = run(pytest_cmd, cwd=clone_dir, check=False)
    # Exit 5 ("no tests collected") is only an honest outcome for subjects whose
    # test suite was deliberately stripped. A non-stripped subject exiting 5 means
    # its own test suite silently failed to collect -- that's a real failure, not
    # an expected post-strip state, and must not be papered over as smoke-ok.
    if subject.get("strip_tests"):
        smoke_ok = smoke.returncode in (0, 5)
    else:
        smoke_ok = smoke.returncode == 0

    mutmut_check = run([str(VENV_PYTHON), "-m", "mutmut", "--version"], cwd=clone_dir, check=False)
    mutmut_ok = mutmut_check.returncode == 0

    ok = smoke_ok and mutmut_ok
    detail = "ok" if ok else f"pytest_rc={smoke.returncode} mutmut_rc={mutmut_check.returncode}"
    return ok, detail


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="prepare only this subject name")
    args = parser.parse_args()

    subjects = json.loads(SUBJECTS_JSON.read_text())["subjects"]
    if args.only:
        subjects = [s for s in subjects if s["name"] == args.only]
        if not subjects:
            raise SystemExit(f"no subject named {args.only!r} in subjects.json")

    results = []
    for subject in subjects:
        name = subject["name"]
        try:
            ok, detail = prepare(subject)
        except Exception as exc:  # noqa: BLE001 -- report, don't crash the whole batch
            ok, detail = False, str(exc).splitlines()[0][:200]
        results.append((name, ok, detail))
        print(f"{'PREPARED' if ok else 'FAILED':10} {name:20} {detail}")

    print()
    print(f"{sum(1 for _, ok, _ in results if ok)}/{len(results)} subjects prepared")
    if not all(ok for _, ok, _ in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
