#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonl_diagram_core.render_audit import evaluate_render_audit, receipt_bytes


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations-a", type=Path, required=True)
    parser.add_argument("--observations-b", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = evaluate_render_audit(
        load(args.observations_a),
        load(args.observations_b),
        load(args.policy),
        load(args.runtime),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(receipt_bytes(receipt))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("result", {}).get("decision") == "ALLOW" and receipt.get("result", {}).get("risk") == "CLEAN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
