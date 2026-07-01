from __future__ import annotations
from typing import Any

JsonObj = dict[str, Any]

def grid_free_layout(dvm: JsonObj) -> JsonObj:
    groups = list(dvm.get("groups", []))
    nodes = list(dvm.get("nodes", []))
    lanes = [g for g in groups if g.get("kind") in {"lane", "region", "column", "row"}]
    if not lanes:
        lane_ids = sorted({n.get("lane") or n.get("group") or "default" for n in nodes})
        lanes = [{"id": lane, "label": lane, "order": i} for i, lane in enumerate(lane_ids)]
    row_index = {g["id"]: i for i, g in enumerate(sorted(lanes, key=lambda x: (x.get("order", 10000), x.get("id", ""))))}
    counters = {key: 0 for key in row_index}
    placements: list[JsonObj] = []
    overlays: list[JsonObj] = []
    for n in sorted(nodes, key=lambda x: (x.get("order", 10000), x.get("id", ""))):
        row_id = n.get("lane") or n.get("group") or next(iter(row_index), "default")
        if row_id not in row_index:
            row_index[row_id] = len(row_index)
            counters[row_id] = 0
        col = counters[row_id]
        counters[row_id] += 1
        cell = {"id": n["id"], "row": row_index[row_id], "rowId": row_id, "col": col, "z": int((n.get("meta") or {}).get("z", 0))}
        placements.append(cell)
        meta = n.get("meta") or {}
        if meta.get("overlay"):
            overlays.append({"id": n["id"], "anchor": meta.get("anchor"), "z": int(meta.get("z", 100))})
    placements.sort(key=lambda p: (p["row"], p["col"], p.get("z", 0), p["id"]))
    return {"schema":"GridFreeLayout.v1", "rows": sorted(row_index, key=row_index.get), "placements": placements, "overlays": overlays}
