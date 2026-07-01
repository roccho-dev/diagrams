from __future__ import annotations
from typing import Any

JsonObj = dict[str, Any]
FORBIDDEN_GEOMETRY_KEYS = {"x", "y", "width", "height", "w", "h", "cx", "cy", "r", "points", "bbox", "geometry"}
MEANING_OPS = {"diagram.init", "group.upsert", "node.upsert", "edge.upsert", "task.upsert", "entity.upsert", "milestone.upsert", "style.intent", "layout.intent"}

def geometry_leaks(events: list[JsonObj]) -> list[str]:
    leaks: list[str] = []
    for idx, event in enumerate(events):
        op = event.get("op")
        if op not in MEANING_OPS:
            leaks.append(f"event[{idx}].op:{op!r}")
        for key in sorted(set(event) & FORBIDDEN_GEOMETRY_KEYS):
            leaks.append(f"event[{idx}].{key}")
        meta = event.get("meta")
        if isinstance(meta, dict):
            for key in sorted(set(meta) & FORBIDDEN_GEOMETRY_KEYS):
                leaks.append(f"event[{idx}].meta.{key}")
    return leaks

def assert_meaning_only(events: list[JsonObj]) -> None:
    leaks = geometry_leaks(events)
    if leaks:
        raise ValueError("geometry leaked into meaning JSONL: " + ", ".join(leaks))

def meaning_summary(events: list[JsonObj]) -> JsonObj:
    assert_meaning_only(events)
    counts: dict[str, int] = {}
    for event in events:
        op = str(event.get("op"))
        counts[op] = counts.get(op, 0) + 1
    return {"schema":"MeaningSummary.v1", "records": len(events), "ops": dict(sorted(counts.items()))}
