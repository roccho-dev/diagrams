from __future__ import annotations

from typing import Any
from .schema import validate_events, validate_event, EventValidationError

JsonObj = dict[str, Any]

TOKEN_TYPE_BY_OP = {
    "diagram.init": "diagram",
    "group.upsert": "group",
    "node.upsert": "node",
    "edge.upsert": "edge",
    "task.upsert": "task",
    "entity.upsert": "entity",
    "milestone.upsert": "milestone",
    "style.intent": "style_intent",
    "layout.intent": "layout_intent",
    "label.update": "label_update",
    "edge.reconnect": "edge_reconnect",
    "lane.assign": "lane_assign",
    "span.update": "span_update",
    "visual.position.set": "visual_position",
    "visual.edge.bendpoint.set": "visual_edge_bendpoint",
}


def tokenize_event(event: JsonObj, index: int = 0, *, strict: bool = True) -> JsonObj:
    errs = validate_event(event, index, strict=strict)
    if errs:
        raise EventValidationError(index, "; ".join(errs), event)
    op = str(event["op"])
    token = {"seq": index, "type": TOKEN_TYPE_BY_OP[op], "op": op, "payload": dict(event)}
    return token


def tokenize_events(events: list[JsonObj], *, strict: bool = True) -> list[JsonObj]:
    validate_events(events, strict=strict)
    return [tokenize_event(event, i, strict=strict) for i, event in enumerate(events)]
