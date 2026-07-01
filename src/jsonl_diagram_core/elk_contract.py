from __future__ import annotations
from typing import Any

JsonObj = dict[str, Any]

def dvm_to_elk_graph(dvm: JsonObj, *, direction: str = "RIGHT") -> JsonObj:
    children = []
    for node in dvm.get("nodes", []):
        label = str(node.get("label", node.get("id", "")))
        children.append({
            "id": node["id"],
            "labels": [{"text": label}],
            "width": max(80, len(label) * 8 + 24),
            "height": 46,
            "properties": {"kind": node.get("kind", "node"), "group": node.get("group")},
        })
    edges = []
    for edge in dvm.get("edges", []):
        edges.append({"id": edge["id"], "sources": [edge["source"]], "targets": [edge["target"]], "labels": [{"text": edge.get("label", "")}]} )
    return {
        "id": dvm.get("diagram", {}).get("id", "diagram"),
        "layoutOptions": {"elk.algorithm": "layered", "elk.direction": direction},
        "children": children,
        "edges": edges,
    }
