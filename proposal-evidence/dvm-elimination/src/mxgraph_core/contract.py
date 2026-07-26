from __future__ import annotations

import math
from typing import Any

Json = dict[str, Any]


class ContractError(ValueError):
    pass


COMMON_META = {"meta"}
OP_FIELDS: dict[str, tuple[set[str], set[str]]] = {
    "diagram.init": (
        {"op", "id", "kind", "label"},
        {"op", "id", "kind", "label", "meta"},
    ),
    "group.upsert": (
        {"op", "id", "kind", "label"},
        {"op", "id", "kind", "label", "order", "group", "meta"},
    ),
    "node.upsert": (
        {"op", "id", "kind", "label"},
        {"op", "id", "kind", "label", "order", "group", "lane", "meta"},
    ),
    "edge.upsert": (
        {"op", "id", "source", "target"},
        {"op", "id", "kind", "source", "target", "label", "order", "meta", "sourceCommandId"},
    ),
    "task.upsert": (
        {"op", "id", "label", "start", "end"},
        {"op", "id", "label", "lane", "group", "start", "end", "order", "meta"},
    ),
    "entity.upsert": (
        {"op", "id", "kind", "label"},
        {"op", "id", "kind", "label", "group", "order", "columns", "meta"},
    ),
    "milestone.upsert": (
        {"op", "id", "label", "start"},
        {"op", "id", "label", "start", "end", "group", "lane", "order", "meta"},
    ),
    "style.intent": (
        {"op", "target", "intent"},
        {"op", "target", "intent", "meta"},
    ),
    "layout.intent": (
        {"op", "target", "intent"},
        {"op", "target", "intent", "meta"},
    ),
    "label.update": (
        {"op", "target", "label"},
        {"op", "target", "label", "sourceCommandId"},
    ),
    "edge.reconnect": (
        {"op", "id", "source", "target"},
        {"op", "id", "source", "target", "sourcePort", "targetPort", "sourceCommandId"},
    ),
    "lane.assign": (
        {"op", "id", "lane"},
        {"op", "id", "lane", "sourceCommandId"},
    ),
    "span.update": (
        {"op", "id", "start", "end"},
        {"op", "id", "start", "end", "sourceCommandId"},
    ),
    "visual.position.set": (
        {"op", "target", "x", "y"},
        {"op", "target", "x", "y", "w", "h", "lock", "sourceCommandId"},
    ),
    "visual.edge.bendpoint.set": (
        {"op", "id", "points"},
        {"op", "id", "points", "sourceCommandId"},
    ),
}

UPSERT_NAMESPACE = {
    "group.upsert": "group",
    "node.upsert": "node",
    "task.upsert": "node",
    "entity.upsert": "node",
    "milestone.upsert": "node",
    "edge.upsert": "edge",
}


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _valid_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not any(ch in value for ch in "\n\r\t")
    )


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def validate_event_shape(event: Json, index: int) -> None:
    _need(isinstance(event, dict), f"event[{index}] must be an object")
    op = event.get("op")
    _need(isinstance(op, str), f"event[{index}].op must be a string")
    _need(op in OP_FIELDS, f"event[{index}] unknown op: {op}")
    required, allowed = OP_FIELDS[op]
    missing = sorted(required - set(event))
    extra = sorted(set(event) - allowed)
    _need(not missing, f"event[{index}] missing fields for {op}: {missing}")
    _need(not extra, f"event[{index}] misplaced fields for {op}: {extra}")

    for key in ("id", "target", "source", "lane", "group"):
        if key in event and event[key] is not None:
            _need(_valid_id(event[key]), f"event[{index}].{key} must be a non-empty id")
    for key in ("sourceCommandId", "sourcePort", "targetPort"):
        if key in event:
            _need(_valid_id(event[key]), f"event[{index}].{key} must be a non-empty id")
    if "label" in event:
        _need(isinstance(event["label"], str), f"event[{index}].label must be a string")
    if "kind" in event:
        _need(_valid_id(event["kind"]), f"event[{index}].kind must be a non-empty id")
    if "order" in event:
        _need(isinstance(event["order"], int) and not isinstance(event["order"], bool), f"event[{index}].order must be integer")
    if "group" in event and "lane" in event:
        _need(False, f"event[{index}] must not set both group and lane")
    if "meta" in event:
        _need(isinstance(event["meta"], dict), f"event[{index}].meta must be object")
    if "columns" in event:
        _need(isinstance(event["columns"], list), f"event[{index}].columns must be array")
    for key in ("start", "end", "x", "y", "w", "h"):
        if key in event:
            _need(_number(event[key]), f"event[{index}].{key} must be finite numeric")
    for key in ("w", "h"):
        if key in event:
            _need(event[key] > 0, f"event[{index}].{key} must be > 0")
    if "start" in event and "end" in event:
        _need(event["start"] <= event["end"], f"event[{index}] start must be <= end")
    if "lock" in event:
        _need(isinstance(event["lock"], bool), f"event[{index}].lock must be boolean")
    if op == "visual.edge.bendpoint.set":
        points = event["points"]
        _need(isinstance(points, list), f"event[{index}].points must be array")
        for pidx, point in enumerate(points):
            _need(isinstance(point, dict), f"event[{index}].points[{pidx}] must be object")
            _need(set(point) == {"x", "y"}, f"event[{index}].points[{pidx}] must contain only x,y")
            _need(_number(point["x"]) and _number(point["y"]), f"event[{index}].points[{pidx}] coordinates must be numeric")


def _resolve_target(
    target: str,
    *,
    diagram_id: str | None,
    groups: set[str],
    nodes: set[str],
    edges: set[str],
) -> str:
    matches: list[str] = []
    if diagram_id == target:
        matches.append("diagram")
    if target in groups:
        matches.append("group")
    if target in nodes:
        matches.append("node")
    if target in edges:
        matches.append("edge")
    _need(matches, f"target missing: {target}")
    _need(len(matches) == 1, f"ambiguous target {target}: {matches}")
    return matches[0]


def _resolve_vertex(value: str, *, context: str, groups: set[str], nodes: set[str]) -> str:
    matches = [kind for kind, values in (("group", groups), ("node", nodes)) if value in values]
    _need(matches, f"{context} missing: {value}")
    _need(len(matches) == 1, f"ambiguous {context} {value}: {matches}")
    return matches[0]


def _register_semantic_id(owners: dict[str, str], raw_id: str, namespace: str) -> None:
    previous = owners.get(raw_id)
    _need(
        previous in {None, namespace},
        f"semantic id must be globally unique: {raw_id} belongs to {previous} and {namespace}",
    )
    owners[raw_id] = namespace


def validate_events(events: list[Json]) -> None:
    _need(isinstance(events, list), "events must be an array")
    diagram_id: str | None = None
    groups: set[str] = set()
    nodes: set[str] = set()
    edges: set[str] = set()
    seen_namespace: dict[tuple[str, str], str] = {}
    semantic_id_owners: dict[str, str] = {}
    group_parents: dict[str, str | None] = {}

    for index, event in enumerate(events):
        validate_event_shape(event, index)
        op = event["op"]
        if op == "diagram.init":
            _need(diagram_id is None, "diagram.init must occur exactly once")
            diagram_id = event["id"]
            _register_semantic_id(semantic_id_owners, diagram_id, "diagram")
            continue

        _need(diagram_id is not None, f"event[{index}] appears before diagram.init")
        namespace = UPSERT_NAMESPACE.get(op)
        if namespace:
            raw_id = event["id"]
            _register_semantic_id(semantic_id_owners, raw_id, namespace)
            key = (namespace, raw_id)
            previous = seen_namespace.get(key)
            if previous is not None and previous != op:
                compatible = namespace == "node" and previous in {"node.upsert", "task.upsert", "entity.upsert", "milestone.upsert"} and op == previous
                _need(compatible, f"incompatible duplicate operation for {namespace}:{raw_id}: {previous} -> {op}")
            seen_namespace[key] = op
            if namespace == "group":
                groups.add(raw_id)
                group_parents[raw_id] = event.get("group")
            elif namespace == "node":
                nodes.add(raw_id)
            else:
                edges.add(raw_id)
            continue

        if op in {"style.intent", "layout.intent", "label.update"}:
            _resolve_target(event["target"], diagram_id=diagram_id, groups=groups, nodes=nodes, edges=edges)
        elif op == "visual.position.set":
            _resolve_vertex(event["target"], context="visual position target", groups=groups, nodes=nodes)
        elif op == "edge.reconnect":
            _need(event["id"] in edges, f"edge.reconnect target missing: {event['id']}")
            _resolve_vertex(event["source"], context="edge source", groups=groups, nodes=nodes)
            _resolve_vertex(event["target"], context="edge target", groups=groups, nodes=nodes)
        elif op == "lane.assign":
            _need(event["id"] in nodes, f"lane.assign target missing: {event['id']}")
            _need(event["lane"] in groups, f"lane.assign lane missing: {event['lane']}")
        elif op == "span.update":
            _need(event["id"] in nodes, f"span.update target missing: {event['id']}")
        elif op == "visual.edge.bendpoint.set":
            _need(event["id"] in edges, f"edge bendpoint target missing: {event['id']}")

    _need(diagram_id is not None, "missing diagram.init")

    # Final reference integrity. References may point to objects appended later only for
    # upsert payloads; update operations above must point to already-existing objects.
    for index, event in enumerate(events):
        op = event["op"]
        if op == "edge.upsert":
            try:
                _resolve_vertex(event["source"], context="edge source", groups=groups, nodes=nodes)
                _resolve_vertex(event["target"], context="edge target", groups=groups, nodes=nodes)
            except ContractError as exc:
                raise ContractError(f"event[{index}] {exc}") from exc
        if op in {"group.upsert", "node.upsert", "task.upsert", "entity.upsert", "milestone.upsert"}:
            parent = event.get("group") or event.get("lane")
            if parent:
                _need(parent in groups, f"event[{index}] parent group missing: {parent}")

    for group_id in sorted(groups):
        seen: set[str] = set()
        current: str | None = group_id
        while current is not None:
            _need(current not in seen, f"group parent cycle: {group_id} -> {current}")
            seen.add(current)
            current = group_parents.get(current)
