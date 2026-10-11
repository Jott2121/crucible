"""The employer-data scanner must catch planted terms, pass a clean tree, and fail closed."""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts" / "scan_blocked_terms.py"
HASH_FILE = ROOT / ".github" / "blocked-terms.sha256"
CI = ROOT / ".github" / "workflows" / "ci.yml"


def _scan(*args: str, cwd: Path = ROOT, blocked_terms: str = "") -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "BLOCKED_TERMS": blocked_terms}
    return subprocess.run(
        [sys.executable, str(SCANNER), *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _hash_line(term: str) -> str:
    result = _scan("--hash", term)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _git_repo(path: Path, files: dict[str, str]) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    return path


def test_committed_hash_file_is_well_formed_and_holds_only_hashes():
    entries = [
        line for line in HASH_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert entries
    assert all(re.fullmatch(r"[0-9a-f]{64} [1-9][0-9]*", line) for line in entries)


def test_clean_tree_passes():
    result = _scan()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "clean" in result.stdout


def test_hashed_word_planted_in_temp_file_is_caught(tmp_path):
    hashes = tmp_path / "terms.sha256"
    hashes.write_text(_hash_line("Zorblax"), encoding="utf-8")
    planted = tmp_path / "notes.md"
    planted.write_text("fine line\nfixture from ZORBLAX payroll\n", encoding="utf-8")
    result = _scan("--hash-file", str(hashes), str(planted))
    assert result.returncode == 1
    assert f"{planted}:2: blocked term" in result.stdout
    assert "zorblax" not in result.stdout.lower()


def test_hashed_two_word_phrase_matches_across_punctuation_and_lines(tmp_path):
    hashes = tmp_path / "terms.sha256"
    hashes.write_text(_hash_line("acme widgets"), encoding="utf-8")
    planted = tmp_path / "data.csv"
    planted.write_text("id,org\n1,Acme-\nWidgets\n2,acme gadgets\n", encoding="utf-8")
    result = _scan("--hash-file", str(hashes), str(planted))
    assert result.returncode == 1
    assert result.stdout.count("blocked term") == 1
    assert f"{planted}:2:" in result.stdout


def test_whole_words_only(tmp_path):
    hashes = tmp_path / "terms.sha256"
    hashes.write_text(_hash_line("lmq"), encoding="utf-8")
    clean = tmp_path / "clean.txt"
    clean.write_text("llmq lmqs xlmq\n", encoding="utf-8")
    assert _scan("--hash-file", str(hashes), str(clean)).returncode == 0


def test_blocked_terms_env_adds_terms_without_echoing_them(tmp_path):
    planted = tmp_path / "results.json"
    planted.write_text('{"site": "Quuxfield Plant 9"}\n', encoding="utf-8")
    result = _scan(str(planted), blocked_terms=" , quuxfield plant ,other")
    assert result.returncode == 1
    assert "blocked term" in result.stdout
    assert "quuxfield" not in (result.stdout + result.stderr).lower()


def test_whole_tree_mode_scans_data_folders_and_paths(tmp_path):
    repo = _git_repo(tmp_path / "repo", {
        "README.md": "clean\n",
        "results/run1/out.txt": "seeded from Zorblax\n",
        "fixtures/zorblax_roster.csv": "a,b\n",
    })
    hashes = tmp_path / "terms.sha256"
    hashes.write_text(_hash_line("zorblax"), encoding="utf-8")
    result = _scan("--hash-file", str(hashes), cwd=repo)
    assert result.returncode == 1
    assert "results/run1/out.txt:1: blocked term" in result.stdout
    assert "fixtures/zorblax_roster.csv: blocked term in path" in result.stdout


def test_generated_junk_dirs_are_skipped(tmp_path):
    repo = _git_repo(tmp_path / "repo", {
        "ok.txt": "clean\n",
        "node_modules/pkg/index.js": "zorblax\n",
    })
    hashes = tmp_path / "terms.sha256"
    hashes.write_text(_hash_line("zorblax"), encoding="utf-8")
    assert _scan("--hash-file", str(hashes), cwd=repo).returncode == 0


def test_export_control_marker_is_caught(tmp_path):
    planted = tmp_path / "doc.md"
    # Built from parts so this test file does not trip the repo-wide scan.
    planted.write_text("EXPORT " + "CONTROLLED\n", encoding="utf-8")
    result = _scan(str(planted))
    assert result.returncode == 1
    assert "export-control marker" in result.stdout


def test_missing_hash_file_fails_closed(tmp_path):
    result = _scan("--hash-file", str(tmp_path / "absent.sha256"))
    assert result.returncode == 2
    assert "missing" in result.stderr


def test_empty_hash_file_fails_closed_even_with_env_terms(tmp_path):
    hashes = tmp_path / "terms.sha256"
    hashes.write_text("# comments only\n\n", encoding="utf-8")
    result = _scan("--hash-file", str(hashes), blocked_terms="zorblax")
    assert result.returncode == 2
    assert "no entries" in result.stderr


def test_malformed_hash_file_fails_closed(tmp_path):
    hashes = tmp_path / "terms.sha256"
    hashes.write_text("zorblax\n", encoding="utf-8")
    assert _scan("--hash-file", str(hashes)).returncode == 2


def test_unreadable_target_fails_closed(tmp_path):
    assert _scan(str(tmp_path / "gone.txt")).returncode == 2


def test_ci_runs_scanner_with_optional_secret():
    ci = CI.read_text(encoding="utf-8")
    assert "python3 scripts/scan_blocked_terms.py" in ci
    assert "BLOCKED_TERMS: ${{ secrets.BLOCKED_TERMS }}" in ci
    assert "':!" not in ci
