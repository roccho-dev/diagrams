#!/usr/bin/env python3
"""Fail when a PR changes paths outside the Issue #8 allowlist."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ALLOWED_EXACT = {
    ".github/workflows/mxfile-composition-proof.yml",
    "docs/architecture/mxfile-composition.md",
}
ALLOWED_PREFIX = "proposal-evidence/mxfile-composition/"
REGULAR_FILE_MODES = {"100644", "100755"}


def is_allowed(path: str) -> bool:
    return path in ALLOWED_EXACT or path.startswith(ALLOWED_PREFIX)


def _decode(token: bytes) -> str:
    return token.decode("utf-8", errors="strict")


def changed_paths(base: str, head: str, cwd: Path | None = None) -> list[str]:
    """Return every path touched by the diff, including both sides of renames."""

    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "--diff-filter=ACMRDTUXB",
            "-z",
            f"{base}...{head}",
        ],
        check=True,
        capture_output=True,
        cwd=cwd,
    )
    tokens = [token for token in result.stdout.split(b"\0") if token]
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        status = _decode(tokens[index])
        index += 1
        if not status:
            raise ValueError("empty git status token")
        path_count = 2 if status[0] in {"R", "C"} else 1
        if index + path_count > len(tokens):
            raise ValueError(f"truncated git name-status output for {status}")
        paths.extend(_decode(token) for token in tokens[index : index + path_count])
        index += path_count
    return paths


def head_file_modes(
    head: str,
    paths: list[str],
    cwd: Path | None = None,
) -> dict[str, str]:
    """Return Git modes for changed paths that still exist at ``head``.

    Deleted paths are absent. Git symlinks (120000), gitlinks (160000), and any
    future non-regular mode are returned so the caller can reject them.
    """

    if not paths:
        return {}
    result = subprocess.run(
        ["git", "--literal-pathspecs", "ls-tree", "-z", head, "--", *paths],
        check=True,
        capture_output=True,
        cwd=cwd,
    )
    modes: dict[str, str] = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            raw_mode, _object_type, _object_id = metadata.split(b" ", 2)
        except ValueError as exc:
            raise ValueError("malformed git ls-tree output") from exc
        modes[_decode(raw_path)] = _decode(raw_mode)
    return modes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        paths = changed_paths(args.base, args.head)
        modes = head_file_modes(args.head, paths)
    except (subprocess.CalledProcessError, UnicodeDecodeError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "detail": str(exc)}, sort_keys=True))
        return 2

    path_rejected = {path for path in paths if not is_allowed(path)}
    mode_rejected = {
        path: mode
        for path, mode in modes.items()
        if mode not in REGULAR_FILE_MODES
    }
    rejected = sorted(path_rejected.union(mode_rejected))
    result = {
        "allowed_count": len(paths) - sum(path in rejected for path in paths),
        "changed_count": len(paths),
        "rejected": rejected,
        "rejected_modes": dict(sorted(mode_rejected.items())),
        "status": "PASS" if not rejected else "FAIL",
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if not rejected else 1


if __name__ == "__main__":
    raise SystemExit(main())
