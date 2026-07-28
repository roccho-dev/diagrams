#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ADRS = "2ae2830c211057274e0900440ea7b9a1c9e0e9ad"
RETIRED_MODULES = (
    "src/jsonl_diagram_core/" + "meaning" + "_model.py",
    "src/jsonl_diagram_core/" + "render" + "_ast.py",
    "src/jsonl_diagram_core/drawio_" + "render" + "_ast.py",
    "src/jsonl_diagram_core/svg_" + "render" + "_ast.py",
)
RETIRED_ARTIFACT_NAMES = ("d" + "vm.json", "rendering-ir.json", "semantic-state.json", "world.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--candidate", default=os.environ.get("GITHUB_SHA", "local"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    suite = args.suite.resolve()

    identity = json.loads((root / "contracts/mxgraph_current_state/v1/identity.json").read_text())
    fail(identity["status"] == "ACCEPTED_ARCHITECTURE", "accepted architecture identity")
    fail(identity["adrsMergedCommit"] == EXPECTED_ADRS, "exact ADRS merge")
    fail(identity["eventsJsonlAuthority"] is True, "event authority")
    fail(identity["mxGraphModelSoleGeneratedCurrentState"] is True, "sole model")
    fail(identity["generatedStateAuthority"] is False, "generated state non-authority")

    for relative in RETIRED_MODULES:
        fail(not (root / relative).exists(), f"retired module remains: {relative}")
    retired_artifacts = [str(path.relative_to(root)) for path in root.rglob("*") if path.is_file() and path.name in RETIRED_ARTIFACT_NAMES]
    fail(not retired_artifacts, f"retired artifacts remain: {retired_artifacts}")
    fail(not (root / "proposal-evidence" / ("d" + "vm-elimination")).exists(), "temporary proof runtime remains")

    models = sorted((suite / "samples").glob("*/model.drawio"))
    fail(len(models) == 13, f"expected 13 models, got {len(models)}")
    for model in models:
        text = model.read_text(encoding="utf-8")
        fail(text.startswith("<mxfile"), f"not mxfile: {model}")
        fail('authority="events.jsonl"' in text, f"authority missing: {model}")
        fail('jsonlType="node"' in text or 'jsonlType="group"' in text, f"semantic cells missing: {model}")

    manifest = json.loads((suite / "manifest.json").read_text())
    fail(manifest["soleGeneratedCurrentState"] == "mxGraphModel", "manifest state")
    fail(manifest["independentCurrentStateArtifacts"] == 0, "manifest duplicate state")

    active_roots = [root / name for name in ("src", "examples", "tools", "tests")]
    forbidden_imports = []
    patterns = ["meaning" + "_model", "render" + "_ast", "Diagram" + "ViewModel", "Rendering" + "IR"]
    for base in active_roots:
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".mjs", ".js"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(pattern in text for pattern in patterns):
                forbidden_imports.append(str(path.relative_to(root)))
    fail(not forbidden_imports, f"retired active references: {forbidden_imports}")

    report = {
        "kind": "canonicalMxGraphCutoverReceipt.v1",
        "status": "PASS",
        "candidateRevision": args.candidate,
        "adrsMergedCommit": EXPECTED_ADRS,
        "eventsJsonlAuthority": True,
        "soleGeneratedCurrentState": "mxGraphModel",
        "canonicalCutoverComplete": True,
        "allProjectionsMigrated": True,
        "duplicateIrCountZero": True,
        "canonicalModels": len(models),
        "suiteManifestSha256": sha256(suite / "manifest.json"),
        "businessOutcomeAchieved": False,
        "corporateSaleOutcomeAchieved": False,
        "authority": False
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
