from __future__ import annotations

from typing import Any
from .io import canonical_json, sha256_text
from .schema import validate_dvm

JsonObj = dict[str, Any]


def _order_key(obj: JsonObj) -> tuple[int, int, str]:
    order = obj.get("order")
    seq = obj.get("_seq")
    # If no explicit semantic order was supplied, preserve append order.
    # Falling back to id is only for externally supplied DVM fragments.
    return (
        int(order) if isinstance(order, int) else 10_000,
        int(seq) if isinstance(seq, int) else 10_000,
        str(obj.get("id", "")),
    )


def _without_internal_fields(obj: JsonObj) -> JsonObj:
    return {k: v for k, v in obj.items() if not k.startswith("_")}


def _node_from_payload(payload: JsonObj, *, kind_override: str | None = None, seq: int | None = None) -> JsonObj:
    meta = dict(payload.get("meta") or {})
    node: JsonObj = {
        "id": payload["id"],
        "kind": kind_override or payload.get("kind", "node"),
        "label": payload.get("label", payload["id"]),
        "group": payload.get("group") or payload.get("lane"),
        "order": payload.get("order", 10_000),
        "meta": meta,
    }
    if seq is not None:
        node["_seq"] = seq
    if payload.get("lane"):
        node["lane"] = payload["lane"]
    if "start" in payload:
        node["start"] = payload["start"]
    if "end" in payload:
        node["end"] = payload["end"]
    return node


def reduce_tokens(tokens: list[JsonObj], *, validate: bool = True) -> JsonObj:
    diagram: JsonObj | None = None
    groups: dict[str, JsonObj] = {}
    nodes: dict[str, JsonObj] = {}
    edges: dict[str, JsonObj] = {}
    styles: list[JsonObj] = []
    layouts: list[JsonObj] = []
    visual_patches: list[JsonObj] = []

    for token in tokens:
        typ = token["type"]
        payload = token["payload"]
        if typ == "diagram":
            diagram = {
                "id": payload["id"],
                "kind": payload["kind"],
                "label": payload["label"],
                "meta": dict(payload.get("meta") or {}),
            }
        elif typ == "group":
            groups[payload["id"]] = {
                "id": payload["id"],
                "kind": payload["kind"],
                "label": payload["label"],
                "group": payload.get("group"),
                "order": payload.get("order", 10_000),
                "meta": dict(payload.get("meta") or {}),
                "_seq": token["seq"],
            }
        elif typ == "node":
            nodes[payload["id"]] = _node_from_payload(payload, seq=token["seq"])
        elif typ == "task":
            nodes[payload["id"]] = _node_from_payload(payload, kind_override="task", seq=token["seq"])
        elif typ == "entity":
            # Preserve the domain kind carried by the authority event, e.g.
            # entity.upsert kind=table.  The operation class is recorded
            # separately so adapters can still render entity/table affordances
            # without degrading the semantic kind in the DVM.
            node = _node_from_payload(payload, seq=token["seq"])
            node["opClass"] = "entity"
            node["entityKind"] = payload.get("kind")
            nodes[payload["id"]] = node
        elif typ == "milestone":
            nodes[payload["id"]] = _node_from_payload(payload, kind_override="milestone", seq=token["seq"])
        elif typ == "edge":
            edges[payload["id"]] = {
                "id": payload["id"],
                "kind": payload.get("kind", "edge"),
                "source": payload["source"],
                "target": payload["target"],
                "label": payload.get("label", ""),
                "order": payload.get("order", 10_000),
                "meta": dict(payload.get("meta") or {}),
                "_seq": token["seq"],
            }
        elif typ == "style_intent":
            styles.append({"seq": token["seq"], **payload})
        elif typ == "layout_intent":
            layouts.append({"seq": token["seq"], **payload})
        elif typ == "label_update":
            target = payload["target"]
            if diagram and diagram.get("id") == target:
                diagram["label"] = payload["label"]
            elif target in nodes:
                nodes[target]["label"] = payload["label"]
            elif target in edges:
                edges[target]["label"] = payload["label"]
            elif target in groups:
                groups[target]["label"] = payload["label"]
            else:
                raise ValueError(f"label.update target missing: {target}")
        elif typ == "edge_reconnect":
            edge = edges.get(payload["id"])
            if edge is None:
                raise ValueError(f"edge.reconnect target missing: {payload['id']}")
            edge["source"] = payload["source"]
            edge["target"] = payload["target"]
            meta = dict(edge.get("meta") or {})
            if "sourcePort" in payload:
                meta["sourcePort"] = payload["sourcePort"]
            if "targetPort" in payload:
                meta["targetPort"] = payload["targetPort"]
            edge["meta"] = meta
        elif typ == "lane_assign":
            node = nodes.get(payload["id"])
            if node is None:
                raise ValueError(f"lane.assign target missing: {payload['id']}")
            node["lane"] = payload["lane"]
            node["group"] = payload["lane"]
        elif typ == "span_update":
            node = nodes.get(payload["id"])
            if node is None:
                raise ValueError(f"span.update target missing: {payload['id']}")
            node["start"] = payload["start"]
            node["end"] = payload["end"]
        elif typ == "visual_position":
            patch = {"seq": token["seq"], "kind": "position", "target": payload["target"], "x": payload["x"], "y": payload["y"]}
            for key in ("w", "h", "lock"):
                if key in payload:
                    patch[key] = payload[key]
            visual_patches.append(patch)
        elif typ == "visual_edge_bendpoint":
            visual_patches.append({"seq": token["seq"], "kind": "edge_bendpoint", "edge": payload["id"], "points": list(payload.get("points") or [])})

    if diagram is None:
        raise ValueError("missing diagram.init")

    dvm: JsonObj = {
        "schema": "DiagramViewModel.v1",
        "diagram": diagram,
        "groups": [_without_internal_fields(g) for g in sorted(groups.values(), key=_order_key)],
        "nodes": [_without_internal_fields(n) for n in sorted(nodes.values(), key=_order_key)],
        "edges": [_without_internal_fields(e) for e in sorted(edges.values(), key=_order_key)],
        "styleIntents": styles,
        "layoutIntents": layouts,
        "policies": {
            "eventOrdering": "append-order",
            "duplicateUpsert": "last-write-wins-with-compatible-op",
            "referenceIntegrity": "strict-existing-node-group-lane",
            "semanticVisualSeparation": "visual-patches-are-non-semantic",
        },
    }
    if visual_patches:
        dvm["visualPatches"] = visual_patches
    if validate:
        validate_dvm(dvm)
    dvm["hash"] = sha256_text(canonical_json({k: v for k, v in dvm.items() if k != "hash"}))
    return dvm
