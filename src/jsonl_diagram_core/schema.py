from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

JsonObj = dict[str, Any]

EVENT_RULES: dict[str, dict[str, set[str]]] = {
    "diagram.init": {
        "required": {"op", "id", "kind", "label"},
        "allowed": {"op", "id", "kind", "label", "meta"},
    },
    "group.upsert": {
        "required": {"op", "id", "kind", "label"},
        "allowed": {"op", "id", "kind", "label", "order", "group", "meta"},
    },
    "node.upsert": {
        "required": {"op", "id", "kind", "label"},
        "allowed": {"op", "id", "kind", "label", "order", "group", "lane", "meta"},
    },
    "edge.upsert": {
        "required": {"op", "id", "source", "target"},
        "allowed": {"op", "id", "kind", "label", "source", "target", "order", "sourceCommandId", "meta"},
    },
    "task.upsert": {
        "required": {"op", "id", "lane", "start", "end", "label"},
        "allowed": {"op", "id", "kind", "label", "lane", "start", "end", "order", "meta"},
    },
    "entity.upsert": {
        "required": {"op", "id", "kind", "label", "meta"},
        "allowed": {"op", "id", "kind", "label", "order", "group", "meta"},
    },
    "milestone.upsert": {
        "required": {"op", "id", "kind", "label"},
        "allowed": {"op", "id", "kind", "label", "order", "meta"},
    },
    "style.intent": {
        "required": {"op", "target", "intent"},
        "allowed": {"op", "target", "intent", "meta"},
    },
    "layout.intent": {
        "required": {"op", "target", "intent"},
        "allowed": {"op", "target", "intent", "meta"},
    },
    "label.update": {
        "required": {"op", "target", "label"},
        "allowed": {"op", "target", "label", "sourceCommandId", "meta"},
    },
    "edge.reconnect": {
        "required": {"op", "id", "source", "target"},
        "allowed": {"op", "id", "source", "target", "sourcePort", "targetPort", "sourceCommandId", "meta"},
    },
    "lane.assign": {
        "required": {"op", "id", "lane"},
        "allowed": {"op", "id", "lane", "sourceCommandId", "meta"},
    },
    "span.update": {
        "required": {"op", "id", "start", "end"},
        "allowed": {"op", "id", "start", "end", "sourceCommandId", "meta"},
    },
    "visual.position.set": {
        "required": {"op", "target", "x", "y"},
        "allowed": {"op", "target", "x", "y", "w", "h", "lock", "sourceCommandId", "meta"},
    },
    "visual.edge.bendpoint.set": {
        "required": {"op", "id", "points"},
        "allowed": {"op", "id", "points", "sourceCommandId", "meta"},
    },
}

ID_FIELDS_BY_OP: dict[str, tuple[str, ...]] = {
    "diagram.init": ("id", "kind"),
    "group.upsert": ("id", "kind", "group"),
    "node.upsert": ("id", "kind", "group", "lane"),
    "edge.upsert": ("id", "kind", "source", "target"),
    "task.upsert": ("id", "kind", "lane"),
    "entity.upsert": ("id", "kind", "group"),
    "milestone.upsert": ("id", "kind"),
    "style.intent": ("target", "intent"),
    "layout.intent": ("target", "intent"),
    "label.update": ("target",),
    "edge.reconnect": ("id", "source", "target"),
    "lane.assign": ("id", "lane"),
    "span.update": ("id",),
    "visual.position.set": ("target",),
    "visual.edge.bendpoint.set": ("id",),
}


@dataclass(frozen=True)
class EventValidationError(Exception):
    index: int
    message: str
    event: JsonObj

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"event[{self.index}]: {self.message}"


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not _is_bool(value)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not _is_bool(value)


def _is_safe_id(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and all(ch not in value for ch in "\n\r\t")


def _check_optional_id(event: JsonObj, key: str, errors: list[str]) -> None:
    if key in event and not _is_safe_id(event[key]):
        errors.append(f"{key} must be a non-empty single-line string")


def _check_meta(event: JsonObj, errors: list[str]) -> None:
    if "meta" in event and not isinstance(event["meta"], dict):
        errors.append("meta must be an object")


def _check_order(event: JsonObj, errors: list[str]) -> None:
    if "order" in event and not _is_int(event["order"]):
        errors.append("order must be an integer")


def validate_event(event: JsonObj, index: int = 0, *, strict: bool = True) -> list[str]:
    errors: list[str] = []
    if not isinstance(event, dict):
        return ["event must be an object"]
    op = event.get("op")
    if not isinstance(op, str):
        return ["missing string op"]
    rule = EVENT_RULES.get(op)
    if rule is None:
        return [f"unknown op: {op}"]

    missing = sorted(k for k in rule["required"] if k not in event)
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
    if strict:
        extra = sorted(set(event) - rule["allowed"])
        if extra:
            errors.append(f"unexpected fields: {', '.join(extra)}")

    for key in ID_FIELDS_BY_OP.get(op, ()):
        _check_optional_id(event, key, errors)
    if "sourceCommandId" in event and not _is_safe_id(event["sourceCommandId"]):
        errors.append("sourceCommandId must be a non-empty single-line string")
    if "label" in event and not isinstance(event["label"], str):
        errors.append("label must be a string")
    _check_meta(event, errors)
    _check_order(event, errors)

    if op == "entity.upsert":
        meta = event.get("meta")
        if isinstance(meta, dict):
            cols = meta.get("columns")
            if not isinstance(cols, list):
                errors.append("entity.upsert requires meta.columns list")
            else:
                for i, col in enumerate(cols):
                    if isinstance(col, str):
                        continue
                    if isinstance(col, list) and col and all(isinstance(x, str) for x in col):
                        continue
                    errors.append(f"entity.upsert meta.columns[{i}] must be string or non-empty string list")
        else:
            errors.append("entity.upsert requires meta object with columns")

    if op == "task.upsert":
        if not _is_int(event.get("start")) or not _is_int(event.get("end")):
            errors.append("task.upsert requires integer start/end")
        elif event["end"] <= event["start"]:
            errors.append("task.upsert requires end > start")

    if op == "milestone.upsert":
        meta = event.get("meta")
        has_when = isinstance(meta, dict) and isinstance(meta.get("when"), str) and bool(meta.get("when", "").strip())
        if "order" not in event and not has_when:
            errors.append("milestone.upsert requires order or meta.when")

    if op == "span.update":
        if not _is_int(event.get("start")) or not _is_int(event.get("end")):
            errors.append("span.update requires integer start/end")
        elif event["end"] <= event["start"]:
            errors.append("span.update requires end > start")

    if op == "visual.position.set":
        if not _is_number(event.get("x")) or not _is_number(event.get("y")):
            errors.append("visual.position.set requires numeric x/y")
        for key in ("w", "h"):
            if key in event and not _is_number(event[key]):
                errors.append(f"visual.position.set {key} must be numeric")
        if "lock" in event and not _is_bool(event["lock"]):
            errors.append("visual.position.set lock must be boolean")

    if op == "visual.edge.bendpoint.set":
        points = event.get("points")
        if not isinstance(points, list):
            errors.append("visual.edge.bendpoint.set requires points list")
        else:
            for i, point in enumerate(points):
                if not isinstance(point, dict) or not _is_number(point.get("x")) or not _is_number(point.get("y")):
                    errors.append(f"visual.edge.bendpoint.set points[{i}] requires numeric x/y")

    return errors


def _id_namespace(op: str) -> str:
    if op in {"node.upsert", "task.upsert", "entity.upsert", "milestone.upsert", "lane.assign", "span.update"}:
        return "node"
    if op in {"edge.upsert", "edge.reconnect", "visual.edge.bendpoint.set"}:
        return "edge"
    if op == "group.upsert":
        return "group"
    if op == "diagram.init":
        return "diagram"
    return op.split(".")[0]


def _compatible_id_reuse(prev_op: str, next_op: str) -> bool:
    # Semantic IDs share one global namespace across diagram, group, node and
    # edge objects. Re-upsert within the same namespace is allowed; cross-kind
    # reuse is rejected before reduction.
    return _id_namespace(prev_op) == _id_namespace(next_op)


def validate_events(events: list[JsonObj], *, strict: bool = True) -> None:
    diagram_init_count = 0
    seen_ids: dict[str, str] = {}
    groups: set[str] = set()
    nodes: set[str] = set()
    edges: set[str] = set()
    diagram_id: str | None = None
    group_parents: dict[str, str | None] = {}

    def reject(index: int, message: str, event: JsonObj) -> None:
        raise EventValidationError(index, message, event)

    def vertex_exists(value: str) -> bool:
        return value in groups or value in nodes

    for i, event in enumerate(events):
        errs = validate_event(event, i, strict=strict)
        if errs:
            reject(i, "; ".join(errs), event)
        op = event["op"]
        if op == "diagram.init":
            diagram_init_count += 1
            diagram_id = str(event["id"])
        if "id" in event and op in {"diagram.init", "group.upsert", "node.upsert", "task.upsert", "entity.upsert", "milestone.upsert", "edge.upsert"}:
            raw_id = str(event["id"])
            prev = seen_ids.get(raw_id)
            if prev and not _compatible_id_reuse(prev, op):
                reject(i, f"id {raw_id!r} reused across incompatible ops: {prev} then {op}", event)
            seen_ids[raw_id] = op

        if op == "group.upsert":
            groups.add(str(event["id"]))
            group_parents[str(event["id"])] = event.get("group")
        elif op in {"node.upsert", "task.upsert", "entity.upsert", "milestone.upsert"}:
            nodes.add(str(event["id"]))
        elif op == "edge.upsert":
            edges.add(str(event["id"]))
        elif op in {"style.intent", "layout.intent", "label.update"}:
            target = str(event["target"])
            matches = sum((target == diagram_id, target in groups, target in nodes, target in edges))
            if matches != 1:
                reject(i, f"target must resolve exactly once: {target}", event)
        elif op == "visual.position.set":
            if not vertex_exists(str(event["target"])):
                reject(i, f"visual position target missing: {event['target']}", event)
        elif op == "edge.reconnect":
            if str(event["id"]) not in edges:
                reject(i, f"edge.reconnect target missing: {event['id']}", event)
            if not vertex_exists(str(event["source"])) or not vertex_exists(str(event["target"])):
                reject(i, "edge.reconnect source/target missing", event)
        elif op == "lane.assign":
            if str(event["id"]) not in nodes or str(event["lane"]) not in groups:
                reject(i, "lane.assign target or lane missing", event)
        elif op == "span.update" and str(event["id"]) not in nodes:
            reject(i, f"span.update target missing: {event['id']}", event)
        elif op == "visual.edge.bendpoint.set" and str(event["id"]) not in edges:
            reject(i, f"edge bendpoint target missing: {event['id']}", event)

    if diagram_init_count != 1:
        reject(0, f"expected exactly one diagram.init, got {diagram_init_count}", events[0] if events else {})

    # Upsert references may point to objects declared later, so validate them
    # against the final object sets after the append stream is known.
    for i, event in enumerate(events):
        op = event["op"]
        if op == "edge.upsert":
            if not vertex_exists(str(event["source"])) or not vertex_exists(str(event["target"])):
                reject(i, "edge source/target missing", event)
        if op in {"group.upsert", "node.upsert", "task.upsert", "entity.upsert", "milestone.upsert"}:
            parent = event.get("group") or event.get("lane")
            if parent and str(parent) not in groups:
                reject(i, f"parent group missing: {parent}", event)

    for group in sorted(groups):
        seen: set[str] = set()
        current: str | None = group
        while current is not None:
            if current in seen:
                reject(0, f"group parent cycle: {group} -> {current}", events[0] if events else {})
            seen.add(current)
            current = group_parents.get(current)


def packaged_schema_path() -> Path | None:
    try:
        return Path(str(resources.files("jsonl_diagram_core.schemas").joinpath("diagram-event.v1.schema.json")))
    except Exception:
        return None
