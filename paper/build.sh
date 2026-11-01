#!/usr/bin/env bash
# Build the paper PDF and the arXiv source archive from paper/crucible.tex.
# Output goes to paper/build/ (not committed). Fails on any LaTeX error.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="$here/build"
rm -rf "$out"
mkdir -p "$out/src"
cp "$here/crucible.tex" "$out/src/"
cd "$out/src"
for _ in 1 2; do
  pdflatex -interaction=nonstopmode -halt-on-error crucible.tex >/dev/null
done
if grep -E "undefined references|Citation .* undefined|Reference .* undefined" crucible.log; then
  echo "unresolved references" >&2
  exit 1
fi
cp crucible.pdf "$out/crucible.pdf"
tar -czf "$out/crucible-arxiv.tar.gz" crucible.tex
echo "built $out/crucible.pdf ($(grep -o 'Output written.*' crucible.log))"
echo "built $out/crucible-arxiv.tar.gz"
