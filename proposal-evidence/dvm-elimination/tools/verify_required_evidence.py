#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_PATHS = (
    "README.md",
    "validation/proof-report.json",
    "validation/source-boundary-scan.txt",
    "validation/manifest.json",
    "gallery/index.html",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_relative(raw: str) -> bool:
    path = Path(raw)
    return bool(raw) and not path.is_absolute() and ".." not in path.parts


def verify_required_evidence(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    for raw in REQUIRED_PATHS:
        path = root / raw
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"required evidence missing or empty: {raw}")

    report_path = root / "validation/proof-report.json"
    if report_path.is_file():
        try:
            report: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("status") != "PASS":
                errors.append(f"proof report is not PASS: {report.get('status')}")
            if report.get("sampleCount") != 13:
                errors.append(f"proof sampleCount must be 13: {report.get('sampleCount')}")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"proof report cannot be read: {exc}")

    models = sorted((root / "generated").glob("*/model.drawio"))
    if len(models) != 13:
        errors.append(f"expected 13 generated model.drawio files, got {len(models)}")
    for model in models:
        if model.stat().st_size == 0:
            errors.append(f"empty generated model: {model.relative_to(root)}")

    manifest_path = root / "validation/manifest.json"
    if manifest_path.is_file():
        try:
            manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = manifest.get("files")
            if not isinstance(entries, list) or not entries:
                errors.append("manifest files must be a non-empty array")
            else:
                seen: set[str] = set()
                for index, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        errors.append(f"manifest entry[{index}] is not an object")
                        continue
                    raw = entry.get("path")
                    if not isinstance(raw, str) or not _safe_relative(raw):
                        errors.append(f"manifest entry[{index}] has unsafe path: {raw!r}")
                        continue
                    if raw in seen:
                        errors.append(f"manifest path duplicated: {raw}")
                        continue
                    seen.add(raw)
                    path = root / raw
                    if not path.is_file():
                        errors.append(f"manifest file missing: {raw}")
                        continue
                    if path.stat().st_size != entry.get("size"):
                        errors.append(f"manifest size mismatch: {raw}")
                    if _sha256(path) != entry.get("sha256"):
                        errors.append(f"manifest sha256 mismatch: {raw}")
                required_manifest_paths = {raw for raw in REQUIRED_PATHS if raw != "validation/manifest.json"}
                required_manifest_paths |= {str(path.relative_to(root)) for path in models}
                for raw in sorted(required_manifest_paths - seen):
                    errors.append(f"required evidence absent from manifest: {raw}")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"manifest cannot be read: {exc}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = verify_required_evidence(args.root)
    result = {"status": "PASS" if not errors else "FAIL", "errors": errors}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
