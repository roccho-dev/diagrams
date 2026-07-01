from __future__ import annotations
import math
from typing import Any

JsonObj = dict[str, Any]

def venn_set_overlap_layout(sets: list[JsonObj], overlaps: list[JsonObj] | None = None, *, radius: int = 160) -> JsonObj:
    if not 1 <= len(sets) <= 4:
        raise ValueError("venn_set_overlap_layout supports 1..4 sets as a deterministic primitive adapter")
    center_x, center_y = 300.0, 280.0
    spread = radius * 0.72
    circles = []
    for idx, s in enumerate(sets):
        angle = (-90 + idx * (360 / max(len(sets), 3))) * math.pi / 180
        circles.append({"id": s["id"], "label": s.get("label", s["id"]), "cx": round(center_x + spread * math.cos(angle), 2), "cy": round(center_y + spread * math.sin(angle), 2), "r": radius, "z": idx})
    labels = []
    for o in overlaps or []:
        members = o.get("sets", [])
        pts = [c for c in circles if c["id"] in members]
        if pts:
            labels.append({"id": o["id"], "label": o.get("label", o["id"]), "x": round(sum(p["cx"] for p in pts)/len(pts), 2), "y": round(sum(p["cy"] for p in pts)/len(pts), 2), "sets": members})
    return {"schema":"VennSetOverlapLayout.v1", "circles": circles, "overlapLabels": labels}
