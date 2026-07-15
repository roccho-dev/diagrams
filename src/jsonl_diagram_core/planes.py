from __future__ import annotations

from typing import Any

JsonObj = dict[str, Any]

LANE_PROGRESS_KINDS = {
    "lane_progress",
    "swimlane",
    "gantt",
    "sequence",
    "timeline",
    "roadmap",
    "kanban",
    "bpmn",
}
GRAPH_KINDS = {
    "flow",
    "state",
    "architecture",
    "dense",
    "dense_dependency",
    "mindmap",
    "nested_ports",
}
TABLE_KINDS = {"erd", "matrix", "table"}
REGION_KINDS = {"venn", "overlap", "region"}

PROFILE_BY_KIND = {
    "lane_progress": "lane-progress",
    "swimlane": "lane-flow",
    "gantt": "schedule",
    "sequence": "causal-sequence",
    "timeline": "timeline",
    "roadmap": "roadmap",
    "kanban": "stage-board",
    "bpmn": "bpmn-lane-surface",
    "flow": "flow-graph",
    "state": "state-graph",
    "architecture": "container-graph",
    "dense": "dense-graph",
    "dense_dependency": "dense-dependency",
    "mindmap": "tree-profile",
    "nested_ports": "container-port-graph",
    "erd": "table-relation",
    "matrix": "matrix",
    "table": "table",
    "venn": "set-overlap",
    "overlap": "set-overlap",
    "region": "region",
}

RULES_BY_KIND = {
    "gantt": ["ScheduleRules"],
    "sequence": ["CausalRules"],
    "bpmn": ["GraphRules", "BPMNRules"],
    "state": ["StateRules"],
    "architecture": ["ContainerRules"],
    "dense": ["DensityPolicy"],
    "dense_dependency": ["DensityPolicy"],
    "mindmap": ["TreeProfile"],
    "nested_ports": ["ContainerRules", "PortRules"],
    "erd": ["TableRules", "RelationRules"],
}


def classify_plane(dvm: JsonObj) -> JsonObj:
    """Classify a DVM into the semantic plane/profile/rules contract.

    This is intentionally small and dependency-free. It replaces diagram-name
    layout branching with a stable semantic layout intent that adapters can use.
    """
    diagram = dvm.get("diagram") or {}
    kind = str(diagram.get("kind") or "").strip()
    if kind in LANE_PROGRESS_KINDS:
        plane = "LaneProgressPlane"
    elif kind in GRAPH_KINDS:
        plane = "GraphPlane"
    elif kind in TABLE_KINDS:
        plane = "TablePlane"
    elif kind in REGION_KINDS:
        plane = "RegionPlane"
    else:
        # Unknown diagram names must still be projected through an explicit
        # profile before they can justify a new core plane.
        plane = "GraphPlane"
    return {
        "schema": "LayoutIntent.v1",
        "diagramId": diagram.get("id"),
        "diagramKind": kind,
        "plane": plane,
        "profile": PROFILE_BY_KIND.get(kind, kind or "graph"),
        "rules": RULES_BY_KIND.get(kind, []),
        "adapterBoundary": {
            "coreImportsAdapter": False,
            "adapterImportsCore": True,
        },
    }


def projection_fingerprint(dvm: JsonObj, *, profile: str) -> JsonObj:
    """Return the semantic IDs that must survive every projection.

    Rendering coordinates and editor-native IDs are intentionally absent.
    """
    lane_ids = sorted(
        g["id"] for g in dvm.get("groups", []) if isinstance(g, dict) and g.get("kind") in {"lane", "participant", "resource"}
    )
    return {
        "schema": "ProjectionFingerprint.v1",
        "profile": profile,
        "diagramId": (dvm.get("diagram") or {}).get("id"),
        "nodeIds": sorted(n["id"] for n in dvm.get("nodes", []) if isinstance(n, dict)),
        "edgeIds": sorted(e["id"] for e in dvm.get("edges", []) if isinstance(e, dict)),
        "laneIds": lane_ids,
    }
