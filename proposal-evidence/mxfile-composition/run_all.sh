#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

python3 -m unittest discover -s "$HERE/tests" -p 'test_*.py' -v

PYTHONHASHSEED=1 TZ=UTC python3 "$HERE/run_proof.py" --output-dir "$TMP/run-a"
(
  cd /
  PYTHONHASHSEED=987654 TZ=JST-9 python3 "$HERE/run_proof.py" --output-dir "$TMP/run-b"
)

diff -ru "$TMP/run-a" "$TMP/run-b"
cmp "$HERE/expected/proof-summary.json" "$TMP/run-a/proof-summary.json"
(
  cd "$TMP/run-a"
  sha256sum -c SHA256SUMS.txt
)
(
  cd "$TMP/run-b"
  sha256sum -c SHA256SUMS.txt
)

if git -C "$HERE" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  TOP=$(git -C "$HERE" rev-parse --show-toplevel)
  git -C "$TOP" diff --exit-code
  if [[ -n "$(git -C "$TOP" status --porcelain --untracked-files=all)" ]]; then
    echo "ERROR: worktree is dirty after proof replay" >&2
    git -C "$TOP" status --short >&2
    exit 1
  fi
fi

echo PASS
