from __future__ import annotations

import base64
import hashlib
import html
import json
import xml.etree.ElementTree as ET
from typing import Any

from .mxgraph_model import parse_model

Json = dict[str, Any]


def _cells(root: ET.Element) -> list[ET.Element]:
    return root.findall("./diagram/mxGraphModel/root//mxCell")


def _cell_map(root: ET.Element) -> dict[str, ET.Element]:
    return {cell.get("id", ""): cell for cell in _cells(root)}


def absolute_bounds(root: ET.Element, cell: ET.Element) -> tuple[float, float, float, float]:
    cells = _cell_map(root)
    geometry = cell.find("mxGeometry")
    if geometry is None: return 0.0, 0.0, 0.0, 0.0
    x, y = float(geometry.get("x", "0")), float(geometry.get("y", "0"))
    w, h = float(geometry.get("width", "0")), float(geometry.get("height", "0"))
    seen: set[str] = set()
    parent = cell.get("parent")
    while parent and parent not in {"0", "1"}:
        if parent in seen: raise ValueError(f"parent cycle: {parent}")
        seen.add(parent)
        parent_cell = cells.get(parent)
        if parent_cell is None: raise ValueError(f"missing parent: {parent}")
        pgeom = parent_cell.find("mxGeometry")
        if pgeom is not None:
            x += float(pgeom.get("x", "0")); y += float(pgeom.get("y", "0"))
        parent = parent_cell.get("parent")
    return x, y, w, h


def _typed(root: ET.Element, kind: str) -> list[ET.Element]:
    return sorted((cell for cell in _cells(root) if cell.get("jsonlType") == kind), key=lambda cell:(int(cell.get("semanticOrder","10000")), int(cell.get("eventSeq","10000")), cell.get("jsonlId","")))


def _diagram(root: ET.Element) -> ET.Element:
    values = _typed(root, "diagram")
    if len(values) != 1: raise ValueError("exactly one semantic diagram cell required")
    return values[0]


def _edge_points(root: ET.Element, edge: ET.Element) -> list[tuple[float, float]]:
    cells = _cell_map(root)
    source, target = cells.get(edge.get("source", "")), cells.get(edge.get("target", ""))
    if source is None or target is None: return []
    sx, sy, sw, sh = absolute_bounds(root, source); tx, ty, tw, th = absolute_bounds(root, target)
    points = [(sx + sw/2, sy + sh/2)]
    geometry = edge.find("mxGeometry")
    if geometry is not None:
        points.extend((float(p.get("x","0")), float(p.get("y","0"))) for p in geometry.findall("./Array[@as='points']/mxPoint"))
    points.append((tx + tw/2, ty + th/2))
    return points


def render_svg(xml_text: str, *, events_sha256: str | None = None) -> str:
    root = parse_model(xml_text)
    model = root.find("./diagram/mxGraphModel"); assert model is not None
    width, height = float(model.get("pageWidth","1000")), float(model.get("pageHeight","720"))
    title = html.escape(_diagram(root).get("value", ""))
    snapshot = semantic_snapshot(xml_text)
    model_sha = hashlib.sha256(xml_text.encode()).hexdigest()
    source_sha = events_sha256 or model_sha
    provenance = {
        "schema": "SvgProvenance.v2", "generatedFrom": "jsonl", "authority": "events.jsonl",
        "eventsSha256": source_sha, "modelSha256": model_sha,
        "nodeIds": [item["id"] for item in snapshot["nodes"]],
        "edgeIds": [item["id"] for item in snapshot["edges"]],
        "groupIds": [item["id"] for item in snapshot["groups"]],
    }
    metadata = html.escape(json.dumps(provenance, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" data-generated-from="jsonl" data-authority="events.jsonl">', f'<metadata id="jsonl-diagram-provenance">{metadata}</metadata>', '<rect width="100%" height="100%" fill="#fff"/>', '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#334155"/></marker></defs>', f'<text x="38" y="42" font-family="sans-serif" font-size="22" font-weight="700">{title}</text>']
    for cell in _typed(root, "group"):
        x,y,w,h = absolute_bounds(root, cell); label = html.escape(cell.get("value", ""))
        if "ellipse" in cell.get("style", ""):
            parts += [f'<ellipse data-jsonl-id="{html.escape(cell.get("jsonlId",""))}" cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="#6c8ebf" fill-opacity=".18" stroke="#6c8ebf" stroke-width="2"/>', f'<text x="{x+16}" y="{y+26}" font-family="sans-serif" font-size="14" font-weight="700">{label}</text>']
        else:
            parts += [f'<rect data-jsonl-id="{html.escape(cell.get("jsonlId",""))}" x="{x}" y="{y}" width="{w}" height="{h}" fill="#dae8fc" fill-opacity=".2" stroke="#6c8ebf"/>', f'<text x="{x+10}" y="{y+22}" font-family="sans-serif" font-size="14" font-weight="700">{label}</text>']
    for edge in _typed(root, "edge"):
        points = _edge_points(root, edge)
        if len(points) >= 2:
            text = " ".join(f"{x},{y}" for x,y in points)
            parts.append(f'<polyline data-jsonl-id="{html.escape(edge.get("jsonlId",""))}" points="{text}" fill="none" stroke="#334155" stroke-width="1.5" marker-end="url(#arrow)"/>')
    for cell in _typed(root, "node"):
        x,y,w,h = absolute_bounds(root, cell); label = html.escape(cell.get("value", "")); style = cell.get("style", "")
        if "ellipse" in style:
            parts.append(f'<ellipse data-jsonl-id="{html.escape(cell.get("jsonlId",""))}" cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="#fff" stroke="#334155"/>')
        elif "rhombus" in style:
            points = f"{x+w/2},{y} {x+w},{y+h/2} {x+w/2},{y+h} {x},{y+h/2}"
            parts.append(f'<polygon data-jsonl-id="{html.escape(cell.get("jsonlId",""))}" points="{points}" fill="#fff7ed" stroke="#f59e0b"/>')
        else:
            parts.append(f'<rect data-jsonl-id="{html.escape(cell.get("jsonlId",""))}" x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff" stroke="#334155"/>')
        parts.append(f'<text x="{x+w/2}" y="{y+h/2+5}" text-anchor="middle" font-family="sans-serif" font-size="13">{label}</text>')
    parts.append('</svg>')
    text = "".join(parts)
    ET.fromstring(text)
    return text + "\n"


def render_text(xml_text: str) -> str:
    root = parse_model(xml_text); diagram = _diagram(root)
    lines = [f"{diagram.get('value','')} [{diagram.get('semanticKind','')}]", ""]
    for typ in ("group", "node"):
        lines.append(typ + "s")
        for cell in _typed(root, typ):
            parent = cell.get("semanticGroup") or cell.get("semanticLane")
            lines.append(f"  - {cell.get('jsonlId')}: {cell.get('value','')} ({cell.get('semanticKind')})" + (f" in {parent}" if parent else ""))
    lines.append("edges")
    for edge in _typed(root, "edge"):
        lines.append(f"  - {edge.get('semanticSource')} -> {edge.get('semanticTarget')} [{edge.get('value','')}]")
    return "\n".join(lines) + "\n"


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_dot(xml_text: str) -> str:
    root = parse_model(xml_text); lines = ["digraph G {", "  rankdir=LR;", "  node [shape=box];"]
    ids = set()
    for cell in [*_typed(root,"group"), *_typed(root,"node")]:
        raw = cell.get("jsonlId", ""); ids.add(raw)
        shape = "folder" if cell.get("jsonlType") == "group" else "box"
        lines.append(f"  {_quote(raw)} [label={_quote(cell.get('value',''))}, shape={shape}];")
    for edge in _typed(root, "edge"):
        source, target = edge.get("semanticSource",""), edge.get("semanticTarget","")
        if source in ids and target in ids:
            label = f" [label={_quote(edge.get('value',''))}]" if edge.get("value") else ""
            lines.append(f"  {_quote(source)} -> {_quote(target)}{label};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_d2(xml_text: str) -> str:
    root = parse_model(xml_text); lines = ["direction: right"]
    ids = set()
    for cell in [*_typed(root,"group"), *_typed(root,"node")]:
        raw = cell.get("jsonlId", ""); ids.add(raw); lines.append(f"{_quote(raw)}: {_quote(cell.get('value',''))}")
    for edge in _typed(root, "edge"):
        source, target = edge.get("semanticSource",""), edge.get("semanticTarget","")
        if source in ids and target in ids:
            label = f": {_quote(edge.get('value',''))}" if edge.get("value") else ""
            lines.append(f"{_quote(source)} -> {_quote(target)}{label}")
    return "\n".join(lines) + "\n"


def render_image_drawio(xml_text: str) -> str:
    root = parse_model(xml_text); model = root.find("./diagram/mxGraphModel"); assert model is not None
    svg = render_svg(xml_text); data = base64.b64encode(svg.encode()).decode()
    mxfile = ET.Element("mxfile", {"host":"app.diagrams.net", "agent":"image-exact-proof"})
    diagram = ET.SubElement(mxfile, "diagram", {"id":"image-exact", "name":"SVG exact"})
    image_model = ET.SubElement(diagram, "mxGraphModel", {"pageWidth":model.get("pageWidth","1000"), "pageHeight":model.get("pageHeight","720")})
    cells = ET.SubElement(image_model, "root")
    ET.SubElement(cells, "mxCell", {"id":"0"}); ET.SubElement(cells, "mxCell", {"id":"1", "parent":"0"})
    cell = ET.SubElement(cells, "mxCell", {"id":"svg_image_exact", "vertex":"1", "parent":"1", "jsonlType":"imageExact", "style":f"shape=image;imageAspect=0;aspect=fixed;image=data:image/svg+xml;base64,{data};"})
    ET.SubElement(cell, "mxGeometry", {"x":"0", "y":"0", "width":model.get("pageWidth","1000"), "height":model.get("pageHeight","720"), "as":"geometry"})
    text = ET.tostring(mxfile, encoding="unicode") + "\n"; ET.fromstring(text); return text


def semantic_snapshot(xml_text: str) -> Json:
    """Return one transient semantic projection derived from mxGraphModel.

    The returned value is never persisted as current state. It exists only to
    feed projection functions and tests during one process execution.
    """
    root = parse_model(xml_text)
    diagram = _diagram(root)

    def decode_meta(cell: ET.Element) -> Json:
        raw = cell.get("metaJson", "{}")
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}

    groups = []
    for cell in _typed(root, "group"):
        groups.append({
            "id": cell.get("jsonlId"),
            "kind": cell.get("semanticKind"),
            "label": cell.get("value", ""),
            "group": cell.get("semanticGroup"),
            "order": int(cell.get("semanticOrder", "10000")),
            "meta": decode_meta(cell),
        })
    nodes = []
    for cell in _typed(root, "node"):
        node: Json = {
            "id": cell.get("jsonlId"),
            "kind": cell.get("semanticKind"),
            "label": cell.get("value", ""),
            "group": cell.get("semanticGroup") or cell.get("semanticLane"),
            "lane": cell.get("semanticLane"),
            "order": int(cell.get("semanticOrder", "10000")),
            "meta": decode_meta(cell),
            "sourceOp": cell.get("sourceOp"),
        }
        for attr, key in (("semanticStart", "start"), ("semanticEnd", "end")):
            value = cell.get(attr)
            if value is not None:
                node[key] = int(value) if value.lstrip("-").isdigit() else float(value)
        if cell.get("opClass"):
            node["opClass"] = cell.get("opClass")
        if cell.get("entityKind"):
            node["entityKind"] = cell.get("entityKind")
        nodes.append(node)
    edges = []
    for cell in _typed(root, "edge"):
        edges.append({
            "id": cell.get("jsonlId"),
            "kind": cell.get("semanticKind"),
            "label": cell.get("value", ""),
            "source": cell.get("semanticSource"),
            "target": cell.get("semanticTarget"),
            "order": int(cell.get("semanticOrder", "10000")),
            "meta": decode_meta(cell),
        })
    return {
        "diagram": {
            "id": diagram.get("jsonlId"),
            "kind": diagram.get("semanticKind"),
            "label": diagram.get("value", ""),
            "meta": decode_meta(diagram),
        },
        "groups": groups,
        "nodes": nodes,
        "edges": edges,
    }


def semantic_counts(xml_text: str) -> Json:
    snapshot = semantic_snapshot(xml_text)
    return {
        "groups": len(snapshot["groups"]),
        "nodes": len(snapshot["nodes"]),
        "edges": len(snapshot["edges"]),
    }
