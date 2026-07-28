#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonl_diagram_core.mxgraph_model import build_model
from jsonl_diagram_core.semantic_conformance import (
    compare_semantics,
    load_json,
    receipt_bytes,
    sha256_bytes,
    sha256_json,
)


def read_events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--expected-contract", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--implementation-revision", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--observed-out", type=Path, required=True)
    parser.add_argument("--provenance-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()

    events_bytes = args.events.read_bytes()
    generator_path = Path(__file__).resolve().parents[1] / "src/jsonl_diagram_core/mxgraph_model.py"
    generator_bytes = generator_path.read_bytes()
    observed = build_model(read_events(args.events)).encode("utf-8")
    provenance = {
        "kind": "diagram.observedProvenance.v1",
        "implementationRevision": args.implementation_revision,
        "implementationSourceDigest": sha256_json({
            "revision": args.implementation_revision,
            "events": sha256_bytes(events_bytes),
            "generator": sha256_bytes(generator_bytes),
        }),
        "generatorDigest": sha256_bytes(generator_bytes),
        "generatedArtifactSha256": sha256_bytes(observed),
        "generatedAt": args.generated_at,
        "origin": "implementation-derived",
        "expectedContentSourceUsed": False,
    }
    receipt = compare_semantics(
        args.expected.read_bytes(),
        observed,
        load_json(args.expected_contract),
        provenance,
    )
    for path in (args.observed_out, args.provenance_out, args.receipt_out):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.observed_out.write_bytes(observed)
    args.provenance_out.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.receipt_out.write_bytes(receipt_bytes(receipt))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["comparison"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
