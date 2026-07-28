from __future__ import annotations

from typing import Any

from .mxgraph_projection import semantic_snapshot

JsonObj = dict[str, Any]


def model_to_elk_graph(model_xml: str) -> JsonObj:
    snapshot = semantic_snapshot(model_xml)
    return {
        "id": snapshot["diagram"]["id"],
        "layoutOptions": {"elk.algorithm": "layered", "elk.direction": "RIGHT"},
        "children": [{"id": node["id"], "width": 132, "height": 58} for node in snapshot["nodes"]],
        "edges": [{"id": edge["id"], "sources": [edge["source"]], "targets": [edge["target"]], "label": edge.get("label", "")} for edge in snapshot["edges"]],
    }
