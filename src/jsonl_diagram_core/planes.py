from __future__ import annotations

from typing import Any

from .mxgraph_projection import semantic_snapshot

JsonObj = dict[str, Any]

LANE_PROGRESS_KINDS = {"swimlane", "gantt", "timeline", "sequence"}
GRAPH_KINDS = {"flow", "dag", "bpmn", "state", "architecture", "dense", "dense_dependency", "mindmap", "nested_ports", "network"}
TABLE_KINDS = {"erd", "matrix", "table"}
REGION_KINDS = {"venn", "overlap", "region"}
PROFILE_BY_KIND = {
    "gantt": "schedule", "sequence": "sequence", "bpmn": "bpmn", "state": "state-machine",
    "architecture": "container-graph", "dense": "dense-graph", "dense_dependency": "dense-dependency",
    "mindmap": "tree-profile", "nested_ports": "container-port-graph", "erd": "table-relation",
    "matrix": "matrix", "table": "table", "venn": "set-overlap", "overlap": "set-overlap", "region": "region",
}
RULES_BY_KIND = {
    "gantt": ["ScheduleRules"], "sequence": ["CausalRules"], "bpmn": ["GraphRules", "BPMNRules"],
    "state": ["StateRules"], "architecture": ["ContainerRules"], "dense": ["DensityPolicy"],
    "dense_dependency": ["DensityPolicy"], "mindmap": ["TreeProfile"],
    "nested_ports": ["ContainerRules", "PortRules"], "erd": ["TableRules", "RelationRules"],
}


def classify_plane(model_xml: str) -> JsonObj:
    diagram = semantic_snapshot(model_xml)["diagram"]
    kind = str(diagram.get("kind") or "").strip()
    if kind in LANE_PROGRESS_KINDS:
        plane = "LaneProgressPlane"
    elif kind in TABLE_KINDS:
        plane = "TablePlane"
    elif kind in REGION_KINDS:
        plane = "RegionPlane"
    else:
        plane = "GraphPlane"
    return {
        "schema": "LayoutIntent.v1", "diagramId": diagram.get("id"), "diagramKind": kind,
        "plane": plane, "profile": PROFILE_BY_KIND.get(kind, kind or "graph"),
        "rules": RULES_BY_KIND.get(kind, []),
        "adapterBoundary": {"coreImportsAdapter": False, "adapterImportsCore": True},
    }


def projection_fingerprint(model_xml: str, *, profile: str) -> JsonObj:
    snapshot = semantic_snapshot(model_xml)
    return {
        "schema": "ProjectionFingerprint.v1", "profile": profile,
        "diagramId": snapshot["diagram"]["id"],
        "nodeIds": sorted(node["id"] for node in snapshot["nodes"]),
        "edgeIds": sorted(edge["id"] for edge in snapshot["edges"]),
        "laneIds": sorted(group["id"] for group in snapshot["groups"] if group.get("kind") in {"lane", "participant", "resource"}),
    }
