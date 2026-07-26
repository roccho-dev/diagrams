#!/usr/bin/env python3
"""Create a CI-only execution receipt bound to checked-out Git and proof bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument(
        "--mode",
        required=True,
        choices=("pr-exact-head", "post-merge", "manual"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        checked_out_sha = git_head()
        if checked_out_sha != args.expected_sha:
            raise ValueError(
                f"checked-out SHA {checked_out_sha} != expected {args.expected_sha}"
            )

        summary = args.proof_dir / "proof-summary.json"
        manifest = args.proof_dir / "SHA256SUMS.txt"
        if not summary.is_file() or not manifest.is_file():
            raise ValueError("proof summary or manifest missing")

        receipt = {
            "checked_out_sha": checked_out_sha,
            "event_name": os.environ.get("GITHUB_EVENT_NAME", "local"),
            "kind": "mxfile.composition.ci-receipt.v1",
            "manifest_sha256": sha256(manifest),
            "mode": args.mode,
            "proof_summary_sha256": sha256(summary),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "repository": os.environ.get("GITHUB_REPOSITORY", "local"),
            "runner_arch": os.environ.get("RUNNER_ARCH", platform.machine()),
            "runner_os": os.environ.get("RUNNER_OS", platform.system()),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "local"),
            "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
            "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF", "local"),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "PASS", "checked_out_sha": checked_out_sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
