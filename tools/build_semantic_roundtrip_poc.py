#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonl_diagram_core.io import write_jsonl
from jsonl_diagram_core.planes import classify_plane, projection_fingerprint
from jsonl_diagram_core.roundtrip import apply_edit_command, reduce_events, reject_edit_command, semantic_hash, visual_hash

TRIPTYCH_EVENTS = [
    {"op": "diagram.init", "id": "triptych", "kind": "swimlane", "label": "Lane progress triptych"},
    {"op": "group.upsert", "id": "lane.sales", "kind": "lane", "label": "Sales", "order": 1},
    {"op": "group.upsert", "id": "lane.ops", "kind": "lane", "label": "Ops", "order": 2},
    {"op": "task.upsert", "id": "n.qualify", "kind": "task", "lane": "lane.sales", "label": "Qualify lead", "start": 1, "end": 3, "order": 1},
    {"op": "task.upsert", "id": "n.contract", "kind": "task", "lane": "lane.ops", "label": "Prepare contract", "start": 3, "end": 5, "order": 2},
    {"op": "edge.upsert", "id": "e.qualify_contract", "source": "n.qualify", "target": "n.contract", "label": "handoff"},
]

GRAPH_EVENTS = [
    {"op": "diagram.init", "id": "graph", "kind": "architecture", "label": "Graph roundtrip"},
    {"op": "group.upsert", "id": "pkg.core", "kind": "package", "label": "Core"},
    {"op": "node.upsert", "id": "n.api", "kind": "component", "label": "API", "group": "pkg.core", "meta": {"ports": ["out"]}},
    {"op": "node.upsert", "id": "n.reducer", "kind": "component", "label": "Reducer", "group": "pkg.core", "meta": {"ports": ["in", "out"]}},
    {"op": "node.upsert", "id": "n.dvm", "kind": "component", "label": "DVM", "group": "pkg.core"},
    {"op": "node.upsert", "id": "n.adapter", "kind": "component", "label": "Adapter"},
    {"op": "node.upsert", "id": "n.proof", "kind": "component", "label": "Proof"},
    {"op": "edge.upsert", "id": "e.api_reducer", "source": "n.api", "target": "n.reducer"},
    {"op": "edge.upsert", "id": "e.reducer_dvm", "source": "n.reducer", "target": "n.dvm"},
    {"op": "edge.upsert", "id": "e.dvm_adapter", "source": "n.dvm", "target": "n.adapter"},
    {"op": "edge.upsert", "id": "e.dvm_proof", "source": "n.dvm", "target": "n.proof"},
    {"op": "edge.upsert", "id": "e.adapter_proof", "source": "n.adapter", "target": "n.proof"},
]

ERD_EVENTS = [
    {"op": "diagram.init", "id": "erd", "kind": "erd", "label": "Table boundary"},
    {"op": "entity.upsert", "id": "tbl.user", "kind": "table", "label": "User", "meta": {"columns": ["id", "email"]}},
    {"op": "entity.upsert", "id": "tbl.order", "kind": "table", "label": "Order", "meta": {"columns": ["id", "user_id"]}},
    {"op": "edge.upsert", "id": "rel.user_order", "source": "tbl.user", "target": "tbl.order", "label": "places"},
]

VENN_EVENTS = [
    {"op": "diagram.init", "id": "venn", "kind": "venn", "label": "Region boundary"},
    {"op": "node.upsert", "id": "set.a", "kind": "set", "label": "A"},
    {"op": "node.upsert", "id": "set.b", "kind": "set", "label": "B"},
    {"op": "node.upsert", "id": "item.ab", "kind": "overlap", "label": "A and B", "meta": {"sets": ["set.a", "set.b"]}},
]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(out: Path, name: str, before: list[dict], result: dict) -> dict:
    d = out / "fixtures" / name
    d.mkdir(parents=True, exist_ok=True)
    write_jsonl(d / "events.before.jsonl", before)
    write_jsonl(d / "events.after.jsonl", result["events"])
    write_json(d / "dvm.after.json", result["dvm"])
    write_json(d / "proof.json", result["proof"])
    return {"fixture": name, "accepted": result["proof"].get("accepted"), "proof": str(d.relative_to(out) / "proof.json")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    summary: list[dict] = []
    triptych = apply_edit_command(
        TRIPTYCH_EVENTS,
        {"schema": "EditCommand.v1", "commandId": "cmd.rename.qualify", "type": "RenameNode", "targetId": "n.qualify", "value": "Qualify enterprise lead"},
        projection_profiles=["swimlane-lr", "gantt-like", "horizontal-sequence"],
    )
    summary.append(write_fixture(out, "lane-progress-triptych", TRIPTYCH_EVENTS, triptych))

    graph = apply_edit_command(
        GRAPH_EVENTS,
        {"schema": "EditCommand.v1", "commandId": "cmd.reconnect.graph", "type": "ReconnectEdge", "edgeId": "e.adapter_proof", "source": "n.adapter", "target": "n.dvm"},
        projection_profiles=["graph"],
    )
    graph_reject = reject_edit_command(
        GRAPH_EVENTS,
        {"schema": "EditCommand.v1", "commandId": "cmd.bad.reconnect", "type": "ReconnectEdge", "edgeId": "e.adapter_proof", "source": "n.adapter", "target": "n.missing"},
    )
    graph["proof"]["rejectCases"] = [graph_reject]
    summary.append(write_fixture(out, "graph-roundtrip", GRAPH_EVENTS, graph))

    visual = apply_edit_command(
        TRIPTYCH_EVENTS,
        {"schema": "EditCommand.v1", "commandId": "cmd.visual.move", "type": "MoveNodeVisual", "targetId": "n.qualify", "x": 120, "y": 240, "lock": True},
        projection_profiles=["swimlane-lr"],
    )
    summary.append(write_fixture(out, "visual-patch-isolation", TRIPTYCH_EVENTS, visual))

    erd_dvm = reduce_events(ERD_EVENTS)
    venn_dvm = reduce_events(VENN_EVENTS)
    boundary = {
        "schema": "TableRegionBoundaryProof.v1",
        "authority": "events.jsonl",
        "generatedIsAuthority": False,
        "table": {"layoutIntent": classify_plane(erd_dvm), "semanticHash": semantic_hash(erd_dvm), "visualHash": visual_hash(erd_dvm)},
        "region": {"layoutIntent": classify_plane(venn_dvm), "semanticHash": semantic_hash(venn_dvm), "visualHash": visual_hash(venn_dvm)},
        "projectionFingerprints": {
            "table": projection_fingerprint(erd_dvm, profile="table-relation"),
            "region": projection_fingerprint(venn_dvm, profile="set-overlap"),
        },
    }
    boundary["ok"] = boundary["table"]["layoutIntent"]["plane"] == "TablePlane" and boundary["region"]["layoutIntent"]["plane"] == "RegionPlane"
    write_json(out / "fixtures" / "table-region-boundary" / "proof.json", boundary)
    summary.append({"fixture": "table-region-boundary", "accepted": boundary["ok"], "proof": "fixtures/table-region-boundary/proof.json"})

    report = {"schema": "SemanticRoundtripPocReport.v1", "status": "PASS", "fixtures": summary}
    if not all(item.get("accepted") for item in summary):
        report["status"] = "FAIL"
    write_json(out / "semantic-roundtrip-report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
