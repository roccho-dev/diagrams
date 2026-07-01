from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JsonObj = dict[str, Any]

NODE_OPS = {"node.upsert", "task.upsert", "entity.upsert", "milestone.upsert"}


def canonical(value: Any) -> Any:
    """Normalize JSON-ish values for semantic comparison."""
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items()) if v is not None}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value


def read_jsonl(path: Path) -> list[JsonObj]:
    rows: list[JsonObj] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - CLI guard
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"{path}:{line_no}: JSONL row must be an object")
        rows.append(obj)
    return rows


def defaulted_order(event_or_node: JsonObj) -> int:
    order = event_or_node.get("order")
    return order if isinstance(order, int) else 10_000


def event_vertex(event: JsonObj) -> JsonObj:
    op = event["op"]
    out: JsonObj = {
        "id": event["id"],
        "opClass": op.split(".")[0],
        "kind": event.get("kind", op.split(".")[0]),
        "label": event.get("label", event["id"]),
        "group": event.get("group") or event.get("lane"),
        "order": defaulted_order(event),
        "meta": dict(event.get("meta") or {}),
    }
    if op == "entity.upsert":
        out["entityKind"] = event.get("kind")
    if "lane" in event:
        out["lane"] = event["lane"]
    if "start" in event:
        out["start"] = event["start"]
    if "end" in event:
        out["end"] = event["end"]
    return canonical(out)


def event_edge(event: JsonObj) -> JsonObj:
    return canonical({
        "id": event["id"],
        "kind": event.get("kind", "edge"),
        "source": event["source"],
        "target": event["target"],
        "label": event.get("label", ""),
        "order": defaulted_order(event),
        "meta": dict(event.get("meta") or {}),
    })


def event_group(event: JsonObj) -> JsonObj:
    return canonical({
        "id": event["id"],
        "kind": event["kind"],
        "label": event["label"],
        "group": event.get("group"),
        "order": defaulted_order(event),
        "meta": dict(event.get("meta") or {}),
    })


def model_from_events(events: list[JsonObj]) -> JsonObj:
    diagram: JsonObj | None = None
    groups: dict[str, JsonObj] = {}
    vertices: dict[str, JsonObj] = {}
    edges: dict[str, JsonObj] = {}
    style: list[JsonObj] = []
    layout: list[JsonObj] = []
    group_order: list[str] = []
    vertex_order: list[str] = []
    edge_order: list[str] = []

    for seq, event in enumerate(events):
        op = event.get("op")
        if op == "diagram.init":
            diagram = canonical({
                "id": event["id"],
                "kind": event["kind"],
                "label": event["label"],
                "meta": dict(event.get("meta") or {}),
            })
        elif op == "group.upsert":
            if event["id"] not in groups:
                group_order.append(event["id"])
            groups[event["id"]] = event_group(event)
        elif op in NODE_OPS:
            if event["id"] not in vertices:
                vertex_order.append(event["id"])
            vertices[event["id"]] = event_vertex(event)
        elif op == "edge.upsert":
            if event["id"] not in edges:
                edge_order.append(event["id"])
            edges[event["id"]] = event_edge(event)
        elif op == "style.intent":
            style.append(canonical({"seq": seq, **event}))
        elif op == "layout.intent":
            layout.append(canonical({"seq": seq, **event}))
        else:
            raise ValueError(f"unknown op in semantic comparator: {op}")
    if diagram is None:
        raise ValueError("missing diagram.init")
    return {
        "diagram": diagram,
        "groups": groups,
        "vertices": vertices,
        "edges": edges,
        "styleIntents": style,
        "layoutIntents": layout,
        "groupOrder": group_order,
        "vertexOrder": vertex_order,
        "edgeOrder": edge_order,
    }


def model_from_dvm(dvm: JsonObj) -> JsonObj:
    diagram = canonical({
        "id": dvm["diagram"]["id"],
        "kind": dvm["diagram"]["kind"],
        "label": dvm["diagram"]["label"],
        "meta": dict(dvm["diagram"].get("meta") or {}),
    })
    groups = {g["id"]: canonical({
        "id": g["id"],
        "kind": g["kind"],
        "label": g["label"],
        "group": g.get("group"),
        "order": defaulted_order(g),
        "meta": dict(g.get("meta") or {}),
    }) for g in dvm.get("groups", [])}
    vertices: dict[str, JsonObj] = {}
    for node in dvm.get("nodes", []):
        op_class = node.get("opClass")
        # node/task/milestone op classes are inferable from kind in these fixtures.
        if op_class is None:
            # kind=task can be a plain node.upsert visual kind (swimlane/BPMN)
            # or a task.upsert scheduled task.  start/end are the semantic
            # discriminator carried by task.upsert fixtures.
            if node.get("kind") == "task" and ("start" in node or "end" in node):
                op_class = "task"
            elif node.get("kind") == "milestone":
                op_class = "milestone"
            else:
                op_class = "node"
        out: JsonObj = {
            "id": node["id"],
            "opClass": op_class,
            "kind": node.get("kind", "node"),
            "label": node.get("label", node["id"]),
            "group": node.get("group") or node.get("lane"),
            "order": defaulted_order(node),
            "meta": dict(node.get("meta") or {}),
        }
        if op_class == "entity":
            out["entityKind"] = node.get("entityKind")
        if "lane" in node:
            out["lane"] = node["lane"]
        if "start" in node:
            out["start"] = node["start"]
        if "end" in node:
            out["end"] = node["end"]
        vertices[node["id"]] = canonical(out)
    edges = {e["id"]: canonical({
        "id": e["id"],
        "kind": e.get("kind", "edge"),
        "source": e["source"],
        "target": e["target"],
        "label": e.get("label", ""),
        "order": defaulted_order(e),
        "meta": dict(e.get("meta") or {}),
    }) for e in dvm.get("edges", [])}
    return {
        "diagram": diagram,
        "groups": groups,
        "vertices": vertices,
        "edges": edges,
        "styleIntents": [canonical(x) for x in dvm.get("styleIntents", [])],
        "layoutIntents": [canonical(x) for x in dvm.get("layoutIntents", [])],
        "groupOrder": [g["id"] for g in dvm.get("groups", [])],
        "vertexOrder": [n["id"] for n in dvm.get("nodes", [])],
        "edgeOrder": [e["id"] for e in dvm.get("edges", [])],
    }


def diff_models(expected: JsonObj, actual: JsonObj, *, prefix: str) -> list[JsonObj]:
    failures: list[JsonObj] = []
    for key in ("diagram", "groups", "vertices", "edges", "styleIntents", "layoutIntents", "groupOrder", "vertexOrder", "edgeOrder"):
        if expected.get(key) != actual.get(key):
            failures.append({
                "where": f"{prefix}.{key}",
                "expected": expected.get(key),
                "actual": actual.get(key),
            })
    return failures


def sample_dirs(root: Path) -> dict[str, Path]:
    return {p.name: p for p in sorted(root.iterdir()) if p.is_dir() and (p / "events.jsonl").exists()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare legacy sample semantics against current JSONL/DVM semantics.")
    parser.add_argument("--legacy", required=True, type=Path, help="legacy samples root containing */events.jsonl")
    parser.add_argument("--current", required=True, type=Path, help="current samples root containing */events.jsonl and optionally dvm.json")
    parser.add_argument("--require-dvm", action="store_true", help="fail when current */dvm.json is missing")
    parser.add_argument("--report", type=Path, help="write JSON report")
    args = parser.parse_args(argv)

    legacy = sample_dirs(args.legacy)
    current = sample_dirs(args.current)
    failures: list[JsonObj] = []
    checked: list[str] = []

    for name, legacy_dir in legacy.items():
        current_dir = current.get(name)
        if current_dir is None:
            failures.append({"sample": name, "where": "sample.exists", "expected": "present", "actual": "missing"})
            continue
        checked.append(name)
        legacy_events = read_jsonl(legacy_dir / "events.jsonl")
        current_events = read_jsonl(current_dir / "events.jsonl")
        legacy_model = model_from_events(legacy_events)
        current_event_model = model_from_events(current_events)
        for failure in diff_models(legacy_model, current_event_model, prefix="events"):
            failure["sample"] = name
            failures.append(failure)
        dvm_path = current_dir / "dvm.json"
        if dvm_path.exists():
            dvm = json.loads(dvm_path.read_text(encoding="utf-8"))
            current_dvm_model = model_from_dvm(dvm)
            for failure in diff_models(legacy_model, current_dvm_model, prefix="dvm"):
                failure["sample"] = name
                failures.append(failure)
        elif args.require_dvm:
            failures.append({"sample": name, "where": "dvm.exists", "expected": "present", "actual": "missing"})

    extra_current = sorted(set(current) - set(legacy))
    report = {
        "schema": "LegacySemanticCompareReport.v1",
        "ok": not failures,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "legacyRoot": str(args.legacy),
        "currentRoot": str(args.current),
        "checkedSamples": checked,
        "legacySampleCount": len(legacy),
        "currentSampleCount": len(current),
        "newSamplesAllowed": extra_current,
        "failures": failures,
        "policy": {
            "eventAuthorityMustMatch": True,
            "generatedDvmMustPreserveDiagramGroupsVerticesEdgesIntents": True,
            "entityKindPreservation": "entity.upsert kind is semantic and must remain DVM node.kind; opClass/entityKind carry operation role",
            "nodeEdgeIdNamespace": "node ids and edge ids are separate semantic namespaces; legacy same-string IDs are preserved",
            "ordering": "append order is semantic when explicit order is absent",
        },
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
