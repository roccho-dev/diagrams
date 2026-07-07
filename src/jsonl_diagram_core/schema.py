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


@dataclass(frozen=True)
class DvmValidationError(Exception):
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


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
    prev_ns = _id_namespace(prev_op)
    next_ns = _id_namespace(next_op)
    if prev_ns == next_ns:
        return True
    # Node and edge identifiers live in separate DVM collections. Allowing
    # the same raw string in both namespaces preserves legacy fixtures such as
    # node id d2 plus edge id d2 without forcing a semantic edge rename.
    return {prev_ns, next_ns} == {"node", "edge"}


def validate_events(events: list[JsonObj], *, strict: bool = True) -> None:
    diagram_init_count = 0
    seen_ids: dict[str, str] = {}
    for i, event in enumerate(events):
        errs = validate_event(event, i, strict=strict)
        if errs:
            raise EventValidationError(i, "; ".join(errs), event)
        op = event["op"]
        if op == "diagram.init":
            diagram_init_count += 1
        if "id" in event:
            raw_id = str(event["id"])
            prev = seen_ids.get(raw_id)
            if prev and not _compatible_id_reuse(prev, op):
                raise EventValidationError(i, f"id {raw_id!r} reused across incompatible ops: {prev} then {op}", event)
            seen_ids[raw_id] = op
    if diagram_init_count != 1:
        raise EventValidationError(0, f"expected exactly one diagram.init, got {diagram_init_count}", events[0] if events else {})


def validate_dvm(dvm: JsonObj) -> None:
    errors: list[str] = []
    diagram = dvm.get("diagram")
    if not isinstance(diagram, dict) or not _is_safe_id(diagram.get("id")):
        errors.append("dvm.diagram.id must exist")
    groups = dvm.get("groups", [])
    nodes = dvm.get("nodes", [])
    edges = dvm.get("edges", [])
    if not isinstance(groups, list) or not isinstance(nodes, list) or not isinstance(edges, list):
        errors.append("dvm groups/nodes/edges must be lists")
        raise DvmValidationError("; ".join(errors))

    group_ids: set[str] = set()
    node_ids: set[str] = set()
    for g in groups:
        gid = g.get("id") if isinstance(g, dict) else None
        if not _is_safe_id(gid):
            errors.append("group id must be non-empty string")
            continue
        if gid in group_ids:
            errors.append(f"duplicate group id: {gid}")
        group_ids.add(gid)
    for n in nodes:
        nid = n.get("id") if isinstance(n, dict) else None
        if not _is_safe_id(nid):
            errors.append("node id must be non-empty string")
            continue
        if nid in node_ids:
            errors.append(f"duplicate node id: {nid}")
        if nid in group_ids:
            errors.append(f"node id collides with group id: {nid}")
        node_ids.add(nid)

    for g in groups:
        if not isinstance(g, dict):
            continue
        parent = g.get("group")
        if parent:
            if parent == g.get("id"):
                errors.append(f"group {g.get('id')} cannot parent itself")
            elif parent not in group_ids:
                errors.append(f"group {g.get('id')} references missing parent group {parent}")
    for n in nodes:
        if not isinstance(n, dict):
            continue
        for key in ("group", "lane"):
            ref = n.get(key)
            if ref and ref not in group_ids:
                errors.append(f"node {n.get('id')} references missing {key} {ref}")
        if ("start" in n or "end" in n) and not (n.get("lane") or n.get("group")):
            errors.append(f"scheduled task {n.get('id')} must have lane or group")
    edge_ids: set[str] = set()
    for e in edges:
        if not isinstance(e, dict):
            errors.append("edge must be object")
            continue
        eid = e.get("id")
        if not _is_safe_id(eid):
            errors.append("edge id must be non-empty string")
        elif eid in edge_ids:
            errors.append(f"duplicate edge id: {eid}")
        edge_ids.add(str(eid))
        src = e.get("source")
        tgt = e.get("target")
        if src not in node_ids:
            errors.append(f"edge {eid} references missing source node {src}")
        if tgt not in node_ids:
            errors.append(f"edge {eid} references missing target node {tgt}")
    target_namespace_counts: dict[str, int] = {}
    for collection in (node_ids, group_ids, edge_ids):
        for item_id in collection:
            target_namespace_counts[item_id] = target_namespace_counts.get(item_id, 0) + 1
    if isinstance(diagram, dict) and diagram.get("id"):
        target_namespace_counts[str(diagram["id"])] = target_namespace_counts.get(str(diagram["id"]), 0) + 1
    valid_targets = set(target_namespace_counts)
    for collection_name in ("styleIntents", "layoutIntents"):
        for item in dvm.get(collection_name, []) or []:
            target = item.get("target") if isinstance(item, dict) else None
            if target not in valid_targets:
                errors.append(f"{collection_name} target missing: {target}")
            elif target_namespace_counts.get(str(target), 0) > 1:
                errors.append(f"{collection_name} target ambiguous across DVM namespaces: {target}")
    for patch in dvm.get("visualPatches", []) or []:
        if not isinstance(patch, dict):
            errors.append("visualPatches item must be object")
            continue
        if patch.get("kind") == "edge_bendpoint":
            edge_id = patch.get("edge")
            if edge_id not in edge_ids:
                errors.append(f"visual edge_bendpoint target missing: {edge_id}")
        else:
            target = patch.get("target")
            if target not in valid_targets:
                errors.append(f"visual patch target missing: {target}")
    if errors:
        raise DvmValidationError("; ".join(errors))


def packaged_schema_path() -> Path | None:
    try:
        return Path(str(resources.files("jsonl_diagram_core.schemas").joinpath("diagram-event.v1.schema.json")))
    except Exception:
        return None
