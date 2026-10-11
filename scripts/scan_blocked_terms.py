#!/usr/bin/env python3
"""Fail-closed scan for blocked employer terms and export-control markers.

Blocked terms are committed only as SHA-256 hashes of their normalized form
(lowercase ASCII words joined by single spaces) in .github/blocked-terms.sha256,
so the guard never has to spell out what it blocks. Every word and run of
adjacent words in each scanned file, and in its path, is normalized, hashed, and
compared. BLOCKED_TERMS (comma-separated, e.g. from a CI secret) adds terms at
runtime. Hits are reported by location and hash prefix only, so a secret term is
never echoed into a public log.

    python scripts/scan_blocked_terms.py              # every tracked file
    python scripts/scan_blocked_terms.py FILE ...     # only these files
    python scripts/scan_blocked_terms.py --hash TERM  # line to add to the hash file

Exit status: 0 clean, 1 hits, 2 configuration or input error. A missing, empty,
or malformed hash file is an error, never a pass.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HASH_FILE = ROOT / ".github" / "blocked-terms.sha256"
SELF = Path(__file__).resolve()

# Generated or vendored trees only. Data folders (results, experiments, fixtures)
# are scanned like everything else.
JUNK_DIRS = frozenset({".git", "node_modules", "build", "dist", "__pycache__", ".venv", "mutants"})

# Readable markers, not hashed: they name a marking, not the employer. This file
# is the only one exempt from them, because it has to spell them out.
# PROPRIETARY is case-sensitive so the English adjective in docs is not a hit.
MARKERS = (
    re.compile(r"\bCUI\b", re.IGNORECASE),
    re.compile(r"\bITAR\b", re.IGNORECASE),
    re.compile(r"EXPORT CONTROLLED", re.IGNORECASE),
    re.compile(r"\bPROPRIETARY\b"),
)

WORD = re.compile(r"[a-z0-9]+")
HASH_LINE = re.compile(r"^([0-9a-f]{64})\s+([1-9][0-9]*)$")


class ConfigError(Exception):
    pass


def normalize(term: str) -> list[str]:
    return WORD.findall(term.lower())


def digest(words: list[str]) -> str:
    return hashlib.sha256(" ".join(words).encode("utf-8")).hexdigest()


def load_hashes(hash_file: Path, extra_terms: str) -> dict[str, int]:
    """Map each blocked-term hash to its word count."""
    if not hash_file.is_file():
        raise ConfigError(f"blocked-terms hash file missing: {hash_file}")
    blocked: dict[str, int] = {}
    for lineno, raw in enumerate(hash_file.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = HASH_LINE.match(line)
        if not match:
            raise ConfigError(f"{hash_file}:{lineno}: expected '<sha256> <word count>'")
        blocked[match.group(1)] = int(match.group(2))
    if not blocked:
        raise ConfigError(f"blocked-terms hash file has no entries: {hash_file}")
    for term in extra_terms.split(","):
        words = normalize(term)
        if words:
            blocked[digest(words)] = len(words)
    return blocked


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ConfigError(f"cannot list tracked files: {exc}") from exc
    files = [Path(p) for p in out.decode("utf-8").split("\0") if p]
    if not files:
        raise ConfigError("no tracked files to scan")
    return [p for p in files if not JUNK_DIRS.intersection(p.parts)]


def _term_hits(
    tokens: list[tuple[str, int]], blocked: dict[str, int], sizes: list[int], cache: dict[str, str | None]
) -> list[tuple[int, str]]:
    hits = []
    words = [t for t, _ in tokens]
    for i, (_, line) in enumerate(tokens):
        for n in sizes:
            if i + n > len(words):
                continue
            phrase = " ".join(words[i : i + n])
            if phrase not in cache:
                h = hashlib.sha256(phrase.encode("utf-8")).hexdigest()
                cache[phrase] = h if blocked.get(h) == n else None
            if cache[phrase]:
                hits.append((line, cache[phrase]))
    return hits


def scan_file(path: Path, blocked: dict[str, int], cache: dict[str, str | None]) -> list[str]:
    sizes = sorted(set(blocked.values()))
    findings = [
        f"{path}: blocked term in path (sha256 {h[:12]})"
        for _, h in _term_hits([(w, 0) for w in normalize(str(path))], blocked, sizes, cache)
    ]
    if path.is_symlink():
        return findings
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if b"\0" in data[:8192]:
        return findings
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    tokens = [(w, n) for n, line in enumerate(lines, 1) for w in WORD.findall(line.lower())]
    findings += [
        f"{path}:{line}: blocked term (sha256 {h[:12]})"
        for line, h in _term_hits(tokens, blocked, sizes, cache)
    ]
    if path.resolve() != SELF:
        for n, line in enumerate(lines, 1):
            for marker in MARKERS:
                if marker.search(line):
                    findings.append(f"{path}:{n}: export-control marker /{marker.pattern}/")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="files to scan (default: every tracked file)")
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH_FILE)
    parser.add_argument("--hash", metavar="TERM", help="print the hash-file line for TERM and exit")
    args = parser.parse_args(argv)

    if args.hash is not None:
        words = normalize(args.hash)
        if not words:
            print("term has no letters or digits", file=sys.stderr)
            return 2
        print(f"{digest(words)} {len(words)}")
        return 0

    try:
        blocked = load_hashes(args.hash_file, os.environ.get("BLOCKED_TERMS", ""))
        files = args.files or tracked_files()
        cache: dict[str, str | None] = {}
        findings = [f for path in files for f in scan_file(path, blocked, cache)]
    except ConfigError as exc:
        print(f"scan_blocked_terms: {exc}", file=sys.stderr)
        return 2

    if findings:
        print("\n".join(findings))
        print(f"scan_blocked_terms: {len(findings)} hit(s) in {len(files)} file(s)", file=sys.stderr)
        return 1
    print(f"scan_blocked_terms: clean ({len(files)} files, {len(blocked)} blocked terms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
