from __future__ import annotations

from typing import Any

from .mxgraph_projection import semantic_snapshot

JsonObj = dict[str, Any]


def grid_free_layout(model_xml: str) -> JsonObj:
    snapshot = semantic_snapshot(model_xml)
    groups = sorted(snapshot["groups"], key=lambda item: (item.get("order", 10000), item["id"]))
    rows = [group["id"] for group in groups]
    row_index = {value: index for index, value in enumerate(rows)}
    counters: dict[str, int] = {}
    placements = []
    overlays = []
    for node in snapshot["nodes"]:
        row = node.get("lane") or node.get("group") or ""
        column = counters.get(row, 0)
        counters[row] = column + 1
        placement = {"id": node["id"], "row": row_index.get(row, 0), "col": column}
        placements.append(placement)
        if node.get("meta", {}).get("overlay"):
            overlays.append({"id": node["id"], "anchor": node.get("meta", {}).get("anchor"), "z": node.get("meta", {}).get("z", 100)})
    return {"schema": "GridFreeLayoutProjection.v2", "source": "mxGraphModel", "rows": rows, "placements": placements, "overlays": overlays}
