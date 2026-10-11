#!/usr/bin/env python3
"""Fail-closed scan for blocked employer terms and export-control markers.

The fail-closed base is .github/blocked-terms.sha256: blocked terms committed only
as SHA-256 hashes of their normalized form (lowercase ASCII words joined by single
spaces), so the guard never has to spell out what it blocks. Every word and run of
adjacent words in each scanned file, and in its path, is normalized, hashed, and
compared. It catches the employer with no secret set.

EMPLOYER_MARKERS (optional, e.g. an Actions secret of the same name) is a regex
alternation matched case-insensitively against every line on top of the hashes.
Hits are reported by location only, never by matched text, so a secret term is
not echoed into a public log.

    python scripts/scan_blocked_terms.py              # every tracked file
    python scripts/scan_blocked_terms.py FILE ...     # only these files
    python scripts/scan_blocked_terms.py --hash TERM  # line to add to the hash file

Exit status: 0 clean, 1 hits, 2 configuration or input error. A missing, empty,
or malformed hash file, or an EMPLOYER_MARKERS that does not compile, is an
error, never a pass.
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

# Generated or vendored trees only. Data folders (results, experiments, fixtures)
# and policy/config folders (.cursor, .github, AGENTS.md) are scanned like
# everything else.
JUNK_DIRS = frozenset({".git", "node_modules", "build", "dist", "__pycache__", ".venv", "mutants"})

# Readable markers, not hashed: they name a marking, not the employer. The
# bracketed letters keep this file from matching its own patterns, so it needs no
# exemption. The last one is case-sensitive so the lowercase adjective is not a hit.
MARKERS = (
    re.compile(r"\bC[U]I\b", re.IGNORECASE),
    re.compile(r"\bIT[A]R\b", re.IGNORECASE),
    re.compile(r"EXPORT[ ]CONTROLLED", re.IGNORECASE),
    re.compile(r"\bPROPRIETAR[Y]\b"),
)

WORD = re.compile(r"[a-z0-9]+")
HASH_LINE = re.compile(r"^([0-9a-f]{64})\s+([1-9][0-9]*)$")


class ConfigError(Exception):
    pass


def normalize(term: str) -> list[str]:
    return WORD.findall(term.lower())


def digest(words: list[str]) -> str:
    return hashlib.sha256(" ".join(words).encode("utf-8")).hexdigest()


def load_hashes(hash_file: Path) -> dict[str, int]:
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
    return blocked


def load_markers(raw: str) -> re.Pattern[str] | None:
    if not raw.strip():
        return None
    try:
        return re.compile(raw, re.IGNORECASE)
    except re.error as exc:
        # The pattern may be secret, so name only the failure.
        raise ConfigError(f"EMPLOYER_MARKERS is not a valid regex ({exc.msg})") from None


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
    tokens: list[tuple[str, int]], blocked: dict[str, int], cache: dict[str, str | None]
) -> list[tuple[int, str]]:
    sizes = sorted(set(blocked.values()))
    words = [t for t, _ in tokens]
    hits = []
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


def scan_file(
    path: Path,
    blocked: dict[str, int],
    extra: re.Pattern[str] | None,
    cache: dict[str, str | None],
) -> list[str]:
    findings = [
        f"{path}: blocked term in path (sha256 {h[:12]})"
        for _, h in _term_hits([(w, 0) for w in normalize(str(path))], blocked, cache)
    ]
    if extra and extra.search(str(path)):
        findings.append(f"{path}: EMPLOYER_MARKERS match in path")
    if path.is_symlink():
        return findings
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if b"\0" in data[:8192]:
        return findings
    lines = data.decode("utf-8", errors="replace").splitlines()
    tokens = [(w, n) for n, line in enumerate(lines, 1) for w in WORD.findall(line.lower())]
    findings += [
        f"{path}:{line}: blocked term (sha256 {h[:12]})"
        for line, h in _term_hits(tokens, blocked, cache)
    ]
    for n, line in enumerate(lines, 1):
        if extra and extra.search(line):
            findings.append(f"{path}:{n}: EMPLOYER_MARKERS match")
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
        blocked = load_hashes(args.hash_file)
        extra = load_markers(os.environ.get("EMPLOYER_MARKERS", ""))
        hash_file = args.hash_file.resolve()
        files = [p for p in (args.files or tracked_files()) if p.resolve() != hash_file]
        cache: dict[str, str | None] = {}
        findings = [f for path in files for f in scan_file(path, blocked, extra, cache)]
    except ConfigError as exc:
        print(f"scan_blocked_terms: {exc}", file=sys.stderr)
        return 2

    if findings:
        print("\n".join(findings))
        print(f"scan_blocked_terms: {len(findings)} hit(s) in {len(files)} file(s)", file=sys.stderr)
        return 1
    extra_note = ", plus EMPLOYER_MARKERS" if extra else ""
    print(f"scan_blocked_terms: clean ({len(files)} files, {len(blocked)} hashed terms{extra_note})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
