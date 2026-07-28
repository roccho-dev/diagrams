from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from typing import Any

from .schema import EventValidationError, validate_events


class ModelValidationError(ValueError):
    pass

Json = dict[str, Any]
NODE_OPS = {"node.upsert", "task.upsert", "entity.upsert", "milestone.upsert"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


def _safe_id(prefix: str, raw: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", raw).strip("_") or "id"
    if stem[0].isdigit():
        stem = "n_" + stem
    suffix = hashlib.sha256(raw.encode()).hexdigest()[:10]
    return f"{prefix}_{stem[:40]}__{suffix}"


def _node(event: Json, seq: int) -> Json:
    op = event["op"]
    kind = "task" if op == "task.upsert" else "milestone" if op == "milestone.upsert" else event.get("kind", "node")
    meta = deepcopy(event.get("meta") or {})
    if "columns" in event:
        meta["columns"] = deepcopy(event["columns"])
    value: Json = {
        "id": event["id"], "kind": kind, "label": event.get("label", event["id"]),
        "group": event.get("group") or event.get("lane"), "lane": event.get("lane"),
        "order": event.get("order", 10000), "meta": meta, "seq": seq, "sourceOp": op,
    }
    for key in ("start", "end"):
        if key in event:
            value[key] = event[key]
    if op == "entity.upsert":
        value["opClass"] = "entity"
        value["entityKind"] = event.get("kind")
    return value


def _reduce(events: list[Json]) -> Json:
    validate_events(events)
    diagram: Json = {}
    groups: dict[str, Json] = {}
    nodes: dict[str, Json] = {}
    edges: dict[str, Json] = {}
    styles: list[Json] = []
    layouts: list[Json] = []
    positions: dict[str, Json] = {}
    bendpoints: dict[str, list[Json]] = {}

    for seq, event in enumerate(events):
        op = event["op"]
        if op == "diagram.init":
            diagram = {"id": event["id"], "kind": event["kind"], "label": event["label"], "meta": deepcopy(event.get("meta") or {})}
        elif op == "group.upsert":
            groups[event["id"]] = {"id": event["id"], "kind": event["kind"], "label": event["label"], "group": event.get("group"), "order": event.get("order", 10000), "meta": deepcopy(event.get("meta") or {}), "seq": seq}
        elif op in NODE_OPS:
            nodes[event["id"]] = _node(event, seq)
        elif op == "edge.upsert":
            edges[event["id"]] = {"id": event["id"], "kind": event.get("kind", "edge"), "source": event["source"], "target": event["target"], "label": event.get("label", ""), "order": event.get("order", 10000), "meta": deepcopy(event.get("meta") or {}), "seq": seq}
        elif op in {"style.intent", "layout.intent"}:
            target = styles if op == "style.intent" else layouts
            target.append({"target": event["target"], "intent": event["intent"], "meta": deepcopy(event.get("meta") or {}), "seq": seq})
        elif op == "label.update":
            target = event["target"]
            if diagram.get("id") == target: diagram["label"] = event["label"]
            elif target in groups: groups[target]["label"] = event["label"]
            elif target in nodes: nodes[target]["label"] = event["label"]
            elif target in edges: edges[target]["label"] = event["label"]
            else: raise ModelValidationError(f"label target missing: {target}")
        elif op == "edge.reconnect":
            edge = edges[event["id"]]
            edge["source"], edge["target"] = event["source"], event["target"]
            for key in ("sourcePort", "targetPort"):
                if key in event: edge["meta"][key] = event[key]
        elif op == "lane.assign":
            nodes[event["id"]]["lane"] = event["lane"]
            nodes[event["id"]]["group"] = event["lane"]
        elif op == "span.update":
            nodes[event["id"]]["start"], nodes[event["id"]]["end"] = event["start"], event["end"]
        elif op == "visual.position.set":
            positions[event["target"]] = {key: event[key] for key in ("x", "y", "w", "h", "lock") if key in event}
        elif op == "visual.edge.bendpoint.set":
            bendpoints[event["id"]] = deepcopy(event["points"])

    key = lambda item: (int(item.get("order", 10000)), int(item.get("seq", 10000)), str(item.get("id", "")))
    return {"diagram": diagram, "groups": sorted(groups.values(), key=key), "nodes": sorted(nodes.values(), key=key), "edges": sorted(edges.values(), key=key), "styles": styles, "layouts": layouts, "positions": positions, "bendpoints": bendpoints}


def _layout(state: Json) -> tuple[dict[str, Json], dict[str, Json]]:
    groups, nodes = state["groups"], state["nodes"]
    group_geom: dict[str, Json] = {}
    node_geom: dict[str, Json] = {}
    if state["diagram"].get("kind") == "venn":
        circles = [(130, 100), (350, 100), (240, 260)]
        set_ids = [g["id"] for g in groups[:3]]
        for i, group in enumerate(groups[:3]):
            group_geom[group["id"]] = {"x": circles[i][0], "y": circles[i][1], "w": 320, "h": 320, "shape": "ellipse"}
        if len(set_ids) == 3:
            a, b, c = set_ids
            positions = {(a,):(188,220), (b,):(518,220), (c,):(352,492), tuple(sorted((a,b))):(352,202), tuple(sorted((a,c))):(278,356), tuple(sorted((b,c))):(428,356), tuple(sorted((a,b,c))):(352,306)}
        else: positions = {}
        for i, node in enumerate(nodes):
            members = tuple(sorted(str(v) for v in node.get("meta", {}).get("members", [])))
            x, y = positions.get(members, (60 + (i % 4) * 170, 560 + (i // 4) * 70))
            node_geom[node["id"]] = {"x": x, "y": y, "w": 146, "h": 38}
        return group_geom, node_geom

    roots = [g for g in groups if not g.get("group")]
    for i, group in enumerate(roots):
        group_geom[group["id"]] = {"x": 40, "y": 86 + i * 190, "w": 820, "h": 160}
    for group in groups:
        if group.get("group"):
            siblings = [g for g in groups if g.get("group") == group["group"]]
            index = siblings.index(group)
            group_geom[group["id"]] = {"x": 24, "y": 42 + index * 105, "w": 760, "h": 90}
    by_parent: dict[str | None, list[Json]] = {}
    for node in nodes:
        by_parent.setdefault(node.get("group") or node.get("lane"), []).append(node)
    for parent, values in by_parent.items():
        for i, node in enumerate(values):
            if parent:
                node_geom[node["id"]] = {"x": 170 + i * 160, "y": 54, "w": 132, "h": 50}
            else:
                node_geom[node["id"]] = {"x": 60 + (i % 4) * 185, "y": 100 + (i // 4) * 100, "w": 138, "h": 54}
    if state["diagram"].get("kind") == "timeline":
        for i, node in enumerate(nodes): node_geom[node["id"]] = {"x": 70 + i * 170, "y": 190, "w": 130, "h": 50}
    return group_geom, node_geom


def _style(kind: str, *, group: bool = False, ellipse: bool = False) -> str:
    if ellipse: return "ellipse;whiteSpace=wrap;html=1;fillColor=#6c8ebf;fillOpacity=18;strokeColor=#6c8ebf;strokeWidth=2;"
    if group: return "shape=rectangle;rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;fillOpacity=12;strokeColor=#6c8ebf;align=left;verticalAlign=top;spacingLeft=10;spacingTop=8;"
    if kind in {"start", "end"}: return "ellipse;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#334155;strokeWidth=1.5;"
    if kind in {"decision", "gateway"}: return "rhombus;whiteSpace=wrap;html=1;fillColor=#fff7ed;strokeColor=#f59e0b;strokeWidth=1.5;"
    return "shape=rectangle;rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#334155;strokeWidth=1.4;"


def _object(root: ET.Element, *, cell_id: str, label: str, attrs: dict[str, str], cell_attrs: dict[str, str], geom: Json) -> ET.Element:
    wrapper = ET.SubElement(root, "object", {"id": cell_id, "label": label, **attrs})
    cell = ET.SubElement(wrapper, "mxCell", dict(cell_attrs))
    ET.SubElement(cell, "mxGeometry", {"x": str(geom.get("x", 0)), "y": str(geom.get("y", 0)), "width": str(geom.get("w", 0)), "height": str(geom.get("h", 0)), "as": "geometry", **({"relative":"1"} if cell_attrs.get("edge") == "1" else {})})
    return cell


def _semantic_attrs(item: Json, typ: str) -> dict[str, str]:
    attrs = {"jsonlType": typ, "jsonlId": str(item["id"]), "semanticKind": str(item.get("kind", typ)), "semanticOrder": str(item.get("order", 10000)), "eventSeq": str(item.get("seq", 10000)), "metaJson": _canonical(item.get("meta") or {})}
    for source, target in (("group","semanticGroup"),("lane","semanticLane"),("start","semanticStart"),("end","semanticEnd"),("opClass","opClass"),("entityKind","entityKind")):
        if item.get(source) is not None: attrs[target] = str(item[source])
    return attrs


def build_model(events: list[Json]) -> str:
    state = _reduce(events)
    group_geom, node_geom = _layout(state)
    for target, patch in state["positions"].items():
        geom = group_geom.get(target) or node_geom.get(target)
        if geom is None: raise ModelValidationError(f"position target missing: {target}")
        geom.update({k:v for k,v in patch.items() if k in {"x","y","w","h","lock"}})

    mxfile = ET.Element("mxfile", {"host":"app.diagrams.net", "agent":"jsonl-diagram-core", "version":"mxgraph-current-state-v1"})
    diagram = ET.SubElement(mxfile, "diagram", {"id":state["diagram"]["id"], "name":"Page-1"})
    model = ET.SubElement(diagram, "mxGraphModel", {"page":"1", "pageWidth":"1000", "pageHeight":"720", "authority":"events.jsonl"})
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id":"0"}); ET.SubElement(root, "mxCell", {"id":"1", "parent":"0"})
    _object(root, cell_id=_safe_id("diagram", state["diagram"]["id"]), label=state["diagram"]["label"], attrs={"jsonlType":"diagram", "jsonlId":state["diagram"]["id"], "semanticKind":state["diagram"]["kind"], "metaJson":_canonical(state["diagram"].get("meta") or {})}, cell_attrs={"vertex":"1", "parent":"1", "style":"text;html=1;opacity=0;"}, geom={"x":0,"y":0,"w":1,"h":1})
    group_ids = {g["id"]:_safe_id("group", g["id"]) for g in state["groups"]}
    node_ids = {n["id"]:_safe_id("node", n["id"]) for n in state["nodes"]}
    endpoint_ids = {**group_ids, **node_ids}
    for group in state["groups"]:
        geom = group_geom[group["id"]]
        attrs = _semantic_attrs(group, "group")
        cell_attrs = {"vertex":"1", "parent":group_ids.get(group.get("group"), "1"), "style":_style(group["kind"], group=True, ellipse=geom.get("shape") == "ellipse")}
        if geom.get("lock"): cell_attrs["locked"] = "1"
        _object(root, cell_id=group_ids[group["id"]], label=group["label"], attrs=attrs, cell_attrs=cell_attrs, geom=geom)
    for node in state["nodes"]:
        geom = node_geom[node["id"]]
        parent = node.get("group") or node.get("lane")
        attrs = {**_semantic_attrs(node, "node"), "sourceOp":node["sourceOp"]}
        cell_attrs = {"vertex":"1", "parent":group_ids.get(parent, "1"), "style":_style(node["kind"])}
        if geom.get("lock"): cell_attrs["locked"] = "1"
        _object(root, cell_id=node_ids[node["id"]], label=node["label"], attrs=attrs, cell_attrs=cell_attrs, geom=geom)
    for edge in state["edges"]:
        cell = _object(root, cell_id=_safe_id("edge", edge["id"]), label=edge["label"], attrs={"jsonlType":"edge", "jsonlId":edge["id"], "semanticKind":edge["kind"], "semanticSource":edge["source"], "semanticTarget":edge["target"], "semanticOrder":str(edge["order"]), "eventSeq":str(edge["seq"]), "metaJson":_canonical(edge.get("meta") or {})}, cell_attrs={"edge":"1", "parent":"1", "source":endpoint_ids[edge["source"]], "target":endpoint_ids[edge["target"]], "style":"endArrow=block;html=1;strokeColor=#334155;"}, geom={})
        points = state["bendpoints"].get(edge["id"])
        if points:
            geometry = cell.find("mxGeometry"); assert geometry is not None
            array = ET.SubElement(geometry, "Array", {"as":"points"})
            for point in points: ET.SubElement(array, "mxPoint", {"x":str(point["x"]), "y":str(point["y"])})
    for typ, intents in (("style_intent", state["styles"]), ("layout_intent", state["layouts"])):
        for item in intents:
            raw_id = f"{typ}:{item['seq']}:{item['target']}"
            _object(root, cell_id=_safe_id(typ, raw_id), label=item["intent"], attrs={"jsonlType":typ, "jsonlId":raw_id, "semanticTarget":item["target"], "semanticIntent":item["intent"], "eventSeq":str(item["seq"]), "metaJson":_canonical(item.get("meta") or {})}, cell_attrs={"vertex":"1", "parent":"1", "style":"text;html=1;opacity=0;"}, geom={"x":0,"y":0,"w":1,"h":1})
    ET.indent(mxfile, space="  ")
    text = ET.tostring(mxfile, encoding="unicode", short_empty_elements=True) + "\n"
    ET.fromstring(text)
    return text


def parse_model(xml_text: str) -> ET.Element:
    root = ET.fromstring(xml_text)
    if root.tag != "mxfile": raise ValueError("root must be mxfile")
    for wrapper in root.findall("./diagram/mxGraphModel/root/object"):
        cell = wrapper.find("mxCell")
        if cell is None: continue
        for key, value in wrapper.attrib.items():
            if key == "label": cell.set("value", value)
            else: cell.set(key, value)
    return root


def _cells(xml_text: str) -> list[ET.Element]:
    return parse_model(xml_text).findall("./diagram/mxGraphModel/root//mxCell")


def _semantic_material(xml_text: str) -> Json:
    values = []
    for cell in _cells(xml_text):
        typ = cell.get("jsonlType")
        if typ not in {"diagram","group","node","edge","style_intent","layout_intent"}: continue
        values.append({key:cell.get(key) for key in ("jsonlType","jsonlId","semanticKind","semanticGroup","semanticLane","semanticStart","semanticEnd","semanticSource","semanticTarget","semanticIntent","semanticOrder","eventSeq","sourceOp","opClass","entityKind","value","metaJson") if cell.get(key) is not None})
    return {"cells": sorted(values, key=lambda v:(v.get("jsonlType",""), int(v.get("eventSeq","10000")), v.get("jsonlId","")))}


def _visual_material(xml_text: str) -> Json:
    values = []
    for z, cell in enumerate(_cells(xml_text)):
        if cell.get("jsonlType") not in {"group","node","edge"}: continue
        geometry = cell.find("mxGeometry")
        geom = dict(geometry.attrib) if geometry is not None else {}
        if geometry is not None:
            geom["points"] = [dict(point.attrib) for point in geometry.findall("./Array[@as='points']/mxPoint")]
        values.append({"id":cell.get("jsonlId"), "parent":cell.get("parent"), "source":cell.get("source"), "target":cell.get("target"), "style":cell.get("style",""), "locked":cell.get("locked") == "1", "geometry":geom, "z":z})
    return {"cells":values}


def semantic_hash(xml_text: str) -> str: return _digest(_semantic_material(xml_text))
def visual_hash(xml_text: str) -> str: return _digest(_visual_material(xml_text))


def command_to_event(command: Json) -> Json:
    typ, cid = command.get("type"), command.get("commandId")
    if typ in {"RenameNode","RenameEdge"}: return {"op":"label.update", "target":command["targetId"], "label":command["value"], "sourceCommandId":cid}
    if typ == "ReconnectEdge": return {"op":"edge.reconnect", "id":command["edgeId"], "source":command["source"], "target":command["target"], "sourceCommandId":cid}
    if typ == "ConnectEdge": return {"op":"edge.upsert", "id":command["edgeId"], "source":command["source"], "target":command["target"], "label":command.get("label", ""), "sourceCommandId":cid}
    if typ == "MoveToLane": return {"op":"lane.assign", "id":command["targetId"], "lane":command["laneId"], "sourceCommandId":cid}
    if typ == "ChangeSpan": return {"op":"span.update", "id":command["targetId"], "start":command["start"], "end":command["end"], "sourceCommandId":cid}
    if typ == "MoveNodeVisual":
        value = {"op":"visual.position.set", "target":command["targetId"], "x":command["x"], "y":command["y"], "sourceCommandId":cid}
        for key in ("w","h","lock"):
            if key in command: value[key] = command[key]
        return value
    if typ == "SetEdgeBendpoint": return {"op":"visual.edge.bendpoint.set", "id":command["edgeId"], "points":command.get("points", []), "sourceCommandId":cid}
    raise ModelValidationError(f"unsupported command: {typ}")


def apply_command(events: list[Json], command: Json) -> Json:
    before = build_model(events)
    candidate = command_to_event(command)
    after_events = [*events, candidate]
    try:
        after = build_model(after_events)
    except Exception as exc:
        return {"events":events, "model":before, "proof":{"accepted":False, "appended":False, "error":str(exc), "semanticHashBefore":semantic_hash(before), "visualHashBefore":visual_hash(before)}}
    return {"events":after_events, "model":after, "proof":{"accepted":True, "appended":True, "event":candidate, "semanticHashBefore":semantic_hash(before), "semanticHashAfter":semantic_hash(after), "visualHashBefore":visual_hash(before), "visualHashAfter":visual_hash(after)}}
