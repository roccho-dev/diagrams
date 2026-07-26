from __future__ import annotations

import base64
import copy
import math
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from typing import Any, Iterable

from .io import canonical_json, sha256_text

JsonObj = dict[str, Any]


@dataclass(frozen=True)
class Rect:
    id: str
    page_id: str
    x: float
    y: float
    width: float
    height: float
    parent: str | None
    value: str

    def signature(self) -> JsonObj:
        return {"id": self.id, "pageId": self.page_id, "x": self.x, "y": self.y, "width": self.width, "height": self.height, "parent": self.parent, "value": self.value}


def _digest(value: Any) -> str:
    return "sha256:" + sha256_text(canonical_json(value))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in list(parent):
        if _local(child.tag) == name:
            return child
    return None


def _decode_page(diagram: ET.Element) -> ET.Element:
    direct = _child(diagram, "mxGraphModel")
    if direct is not None:
        return direct
    text = "".join((diagram.text or "").split())
    if not text:
        raise ValueError("diagram page has no mxGraphModel")
    raw = zlib.decompress(base64.b64decode(text, validate=True), wbits=-15).decode("utf-8")
    return ET.fromstring(urllib.parse.unquote(raw))


def _graphs(root: ET.Element) -> Iterable[tuple[str, ET.Element, ET.Element | None]]:
    if _local(root.tag) == "mxGraphModel":
        yield "page-1", root, None
        return
    if _local(root.tag) != "mxfile":
        raise ValueError("drawio root must be mxfile or mxGraphModel")
    seen: set[str] = set()
    for index, diagram in enumerate([x for x in list(root) if _local(x.tag) == "diagram"], 1):
        page_id = diagram.get("id") or f"page-{index}"
        if page_id in seen:
            raise ValueError(f"duplicate diagram page id: {page_id}")
        seen.add(page_id)
        yield page_id, _decode_page(diagram), diagram


def _root(graph: ET.Element) -> ET.Element:
    root = _child(graph, "root")
    if root is None:
        raise ValueError("mxGraphModel missing root")
    return root


def _items(graph: ET.Element) -> Iterable[tuple[ET.Element, ET.Element, JsonObj]]:
    for item in list(_root(graph)):
        attrs: JsonObj = dict(item.attrib) if _local(item.tag) == "object" else {}
        cell = item if _local(item.tag) == "mxCell" else _child(item, "mxCell")
        if cell is not None:
            yield item, cell, attrs


def _number(value: str | None, *, default: float = 0.0) -> float:
    number = default if value in (None, "") else float(value)
    if not math.isfinite(number):
        raise ValueError("geometry values must be finite")
    return number


def _artifact_kind(root: ET.Element) -> str:
    kinds: set[str] = set()
    for _, graph, _ in _graphs(root):
        for _, _, attrs in _items(graph):
            if attrs.get("role") == "diagram-artifact" and attrs.get("artifactKind"):
                kinds.add(str(attrs["artifactKind"]))
    if len(kinds) > 1:
        raise ValueError("conflicting artifact kinds")
    return next(iter(kinds), "diagram.semantic.v1")


def assert_semantic_drawio(drawio_text: str) -> ET.Element:
    root = ET.fromstring(drawio_text)
    if _artifact_kind(root) != "diagram.semantic.v1":
        raise ValueError("review artifact is not a semantic checker/roundtrip input")
    for _, graph, _ in _graphs(root):
        for _, _, attrs in _items(graph):
            if attrs.get("role") == "decision-overlay":
                raise ValueError("semantic artifact contains decision overlay cells")
    return root


def _page_model(page_id: str, graph: ET.Element) -> tuple[dict[str, Rect], dict[str, JsonObj], list[JsonObj]]:
    cells: dict[str, ET.Element] = {}
    wrappers: dict[str, JsonObj] = {}
    for _, cell, attrs in _items(graph):
        cid = cell.get("id")
        if not cid:
            raise ValueError("mxCell missing id")
        if cid in cells:
            raise ValueError(f"duplicate mxCell id: {cid}")
        cells[cid] = cell
        wrappers[cid] = attrs
    if "0" not in cells or "1" not in cells or cells["1"].get("parent") != "0":
        raise ValueError("root/layer cells 0 and 1 are required")

    local: dict[str, tuple[float, float, float, float]] = {}
    for cid, cell in cells.items():
        if cell.get("vertex") != "1":
            continue
        geom = _child(cell, "mxGeometry")
        if geom is None:
            raise ValueError(f"vertex {cid} missing mxGeometry")
        width, height = _number(geom.get("width")), _number(geom.get("height"))
        if width <= 0 or height <= 0:
            raise ValueError(f"vertex {cid} must have positive geometry")
        local[cid] = (_number(geom.get("x")), _number(geom.get("y")), width, height)

    memo: dict[str, tuple[float, float]] = {}
    visiting: set[str] = set()

    def origin(cid: str) -> tuple[float, float]:
        if cid in memo:
            return memo[cid]
        if cid in visiting:
            raise ValueError(f"parent cycle at {cid}")
        visiting.add(cid)
        cell = cells[cid]
        x, y, _, _ = local[cid]
        parent = cell.get("parent")
        if parent in local:
            px, py = origin(parent)
            x, y = x + px, y + py
        elif parent is not None and parent not in cells:
            raise ValueError(f"missing parent {parent} for {cid}")
        visiting.remove(cid)
        memo[cid] = (x, y)
        return x, y

    rects: dict[str, Rect] = {}
    for cid, (_, _, width, height) in local.items():
        ax, ay = origin(cid)
        rects[cid] = Rect(cid, page_id, ax, ay, width, height, cells[cid].get("parent"), cells[cid].get("value", wrappers[cid].get("label", "")))

    edges: dict[str, JsonObj] = {}
    for cid, cell in cells.items():
        if cell.get("edge") != "1":
            continue
        source, target = cell.get("source"), cell.get("target")
        if not source or not target or source not in rects or target not in rects:
            raise ValueError(f"edge {cid} source/target must reference vertices")
        edges[cid] = {"id": cid, "pageId": page_id, "source": source, "target": target, "value": cell.get("value", wrappers[cid].get("label", ""))}
    semantic_cells = [
        {"pageId": page_id, "id": cid, "attrs": dict(sorted(cell.attrib.items())), "wrapper": dict(sorted(wrappers[cid].items())), "geometry": dict(sorted((_child(cell, "mxGeometry").attrib if _child(cell, "mxGeometry") is not None else {}).items()))}
        for cid, cell in sorted(cells.items())
    ]
    return rects, edges, semantic_cells


def _contains(a: Rect, b: Rect) -> bool:
    return a.x <= b.x and a.y <= b.y and a.x + a.width >= b.x + b.width and a.y + a.height >= b.y + b.height


def _intersection(a: Rect, b: Rect) -> tuple[float, float]:
    w = max(0.0, min(a.x + a.width, b.x + b.width) - max(a.x, b.x))
    h = max(0.0, min(a.y + a.height, b.y + b.height) - max(a.y, b.y))
    return w, h


def _segment_hits_rect_interior(a: tuple[float, float], b: tuple[float, float], rect: Rect) -> bool:
    eps = 1e-9
    xmin, ymin = rect.x + eps, rect.y + eps
    xmax, ymax = rect.x + rect.width - eps, rect.y + rect.height - eps
    if xmin >= xmax or ymin >= ymax:
        return False
    dx, dy = b[0] - a[0], b[1] - a[1]
    p = (-dx, dx, -dy, dy)
    q = (a[0] - xmin, xmax - a[0], a[1] - ymin, ymax - a[1])
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if abs(pi) < eps:
            if qi < 0:
                return False
            continue
        t = qi / pi
        if pi < 0:
            u1 = max(u1, t)
        else:
            u2 = min(u2, t)
        if u1 > u2:
            return False
    return u1 <= u2


def _finding(rule_id: str, rule_class: str, page_id: str, subject_ids: list[str], relation: str, evidence: JsonObj, signatures: list[JsonObj]) -> JsonObj:
    key = "|".join([rule_id, page_id, ",".join(sorted(subject_ids)), relation])
    base: JsonObj = {
        "ruleId": rule_id,
        "ruleClass": rule_class,
        "pageId": page_id,
        "subjectIds": sorted(subject_ids),
        "relationKind": relation,
        "findingKey": key,
        "subjectDigest": _digest(signatures),
        "evidence": evidence,
    }
    base["findingDigest"] = _digest(base)
    return base


def inspect_semantic_drawio(drawio_text: str) -> JsonObj:
    root = assert_semantic_drawio(drawio_text)
    facts: list[JsonObj] = []
    findings: list[JsonObj] = []
    semantic_cells: list[JsonObj] = []
    verification = "COMPLETE"
    for page_id, graph, _ in _graphs(root):
        rects, edges, page_cells = _page_model(page_id, graph)
        semantic_cells.extend(page_cells)
        for aid, a in sorted(rects.items()):
            parent = a.parent
            if parent in rects and not _contains(rects[parent], a):
                findings.append(_finding("model_parent_not_containing", "policy", page_id, [aid, parent], "model-parent", {"child": aid, "parent": parent}, [a.signature(), rects[parent].signature()]))
            for bid, b in sorted(rects.items()):
                if aid >= bid:
                    continue
                w, h = _intersection(a, b)
                area = w * h
                relation = "disjoint" if area == 0 else "contains" if _contains(a, b) else "within" if _contains(b, a) else "partial-overlap"
                facts.append({"pageId": page_id, "kind": "rectangle-relation", "a": aid, "b": bid, "relation": relation, "intersectionArea": area})
                if relation == "partial-overlap":
                    findings.append(_finding("partial_overlap", "policy", page_id, [aid, bid], relation, {"intersectionArea": area}, [a.signature(), b.signature()]))
        for edge_id, edge in sorted(edges.items()):
            source, target = rects[edge["source"]], rects[edge["target"]]
            start = (source.x + source.width / 2, source.y + source.height / 2)
            end = (target.x + target.width / 2, target.y + target.height / 2)
            findings.append(_finding("edge_route_approximate", "coverage", page_id, [edge_id], "center-to-center", {"precision": "approximate"}, [edge]))
            verification = "PARTIAL"
            for obstacle_id, obstacle in sorted(rects.items()):
                if obstacle_id in {source.id, target.id}:
                    continue
                if _segment_hits_rect_interior(start, end, obstacle):
                    findings.append(_finding("edge_crosses_unrelated_rectangle", "policy", page_id, [edge_id, obstacle_id], "edge-obstacle", {"edge": edge_id, "obstacle": obstacle_id}, [edge, obstacle.signature()]))
    model_digest = _digest(semantic_cells)
    return {"schema": "DiagramGeometryReport.v1", "semanticModelDigest": model_digest, "verification": verification, "facts": facts, "findings": sorted(findings, key=lambda x: x["findingKey"])}


def project_review_drawio(drawio_text: str, gate_report: JsonObj, gate_receipt: JsonObj, *, as_of: str) -> tuple[str, JsonObj]:
    geometry = inspect_semantic_drawio(drawio_text)
    if geometry["semanticModelDigest"] != gate_report.get("semanticModelDigest"):
        raise ValueError("gate report semantic digest does not match base")
    if gate_receipt.get("reportDigest") != gate_report.get("reportDigest"):
        raise ValueError("gate receipt does not match report")
    root = copy.deepcopy(assert_semantic_drawio(drawio_text))
    if _local(root.tag) != "mxfile":
        mxfile = ET.Element("mxfile")
        diagram = ET.SubElement(mxfile, "diagram", {"id": "page-1", "name": "Page-1"})
        diagram.append(root)
        root = mxfile
    else:
        for diagram in [x for x in list(root) if _local(x.tag) == "diagram"]:
            graph = _decode_page(diagram)
            attrs = dict(diagram.attrib)
            diagram.clear()
            diagram.attrib.update(attrs)
            diagram.append(graph)

    findings = {f["findingKey"]: f for f in gate_report.get("findings", [])}
    dispositions = {d["findingKey"]: d for d in gate_report.get("dispositions", [])}
    overlay_ids: list[str] = []
    for page_id, graph, _ in _graphs(root):
        page_root = _root(graph)
        layer_id = "overlay-layer-" + sha256_text(page_id + str(gate_receipt.get("receiptId")))[:16]
        ET.SubElement(page_root, "mxCell", {"id": layer_id, "value": "Decision overlay", "parent": "0"})
        meta = ET.SubElement(page_root, "object", {
            "id": "artifact-" + sha256_text(page_id + "review")[:16],
            "role": "diagram-artifact",
            "artifactKind": "diagram.review.v1",
            "semanticModelDigest": str(gate_report["semanticModelDigest"]),
            "gateReceiptId": str(gate_receipt["receiptId"]),
            "asOf": as_of,
        })
        ET.SubElement(meta, "mxCell", {"id": meta.get("id") + "-cell", "parent": layer_id})
        index = 0
        for key in sorted(dispositions):
            finding = findings.get(key)
            disposition = dispositions[key]
            if finding is None or finding.get("pageId") != page_id or disposition.get("state") == "not_required":
                continue
            state = disposition.get("state")
            decision = gate_report.get("decision")
            risk = gate_report.get("risk")
            if state == "accepted":
                label = f"ACCEPTED · {disposition.get('waiverId')} · until {disposition.get('expiresAt')}"
            elif gate_report.get("gateStatus") == "ERROR":
                label = f"ERROR · {key}"
            elif gate_report.get("verification") == "PARTIAL" and finding.get("ruleClass") == "coverage":
                label = f"PARTIAL · {key}"
            else:
                label = f"{decision} · {key}"
            oid = "overlay-" + sha256_text("|".join([page_id, key, str(state), str(gate_receipt.get("receiptId"))]))[:24]
            overlay_ids.append(oid)
            obj_attrs = {
                "id": oid,
                "role": "decision-overlay",
                "overlayId": oid,
                "findingKey": key,
                "targetRefs": ",".join(finding.get("subjectIds", [])),
                "disposition": str(state),
                "verification": str(gate_report.get("verification")),
                "decision": str(decision),
                "risk": str(risk),
                "receiptId": str(gate_receipt.get("receiptId")),
                "label": label,
            }
            if disposition.get("expiresAt"):
                obj_attrs["expiresAt"] = str(disposition["expiresAt"])
            obj = ET.SubElement(page_root, "object", obj_attrs)
            cell = ET.SubElement(obj, "mxCell", {
                "id": oid + "-cell", "value": label, "vertex": "1", "parent": layer_id,
                "style": "rounded=0;whiteSpace=wrap;html=0;align=left;verticalAlign=middle;spacingLeft=6;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=10;",
            })
            ET.SubElement(cell, "mxGeometry", {"x": "8", "y": str(8 + index * 30), "width": "360", "height": "24", "as": "geometry"})
            index += 1
    review_text = ET.tostring(root, encoding="unicode")
    receipt: JsonObj = {
        "schema": "DiagramProjectionReceipt.v1",
        "semanticModelDigest": gate_report["semanticModelDigest"],
        "gateReceiptId": gate_receipt["receiptId"],
        "gateReportDigest": gate_report["reportDigest"],
        "projectorDigest": _digest({"schema": "DecisionOverlayProjector.v1", "placement": "page-status-rail"}),
        "overlayCount": len(overlay_ids),
        "overlayIds": sorted(overlay_ids),
        "reviewModelDigest": "sha256:" + sha256_text(review_text),
        "asOf": as_of,
    }
    receipt["receiptId"] = _digest(receipt)
    return review_text, receipt
