from __future__ import annotations

import html
import json
import math
from typing import Any
from jsonl_diagram_core.io import canonical_json, sha256_text

JsonObj = dict[str, Any]

DEFAULT_TOKENS: JsonObj = {
    "font": "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif",
    "bg": "#f8fafc",
    "ink": "#0f172a",
    "muted": "#64748b",
    "line": "#334155",
    "panel": "#ffffff",
    "panel2": "#eff6ff",
    "accent": "#2563eb",
    "success": "#16a34a",
    "warn": "#f59e0b",
    "danger": "#dc2626",
    "radius": 14,
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def wrap(label: object, max_chars: int = 16) -> list[str]:
    words = str(label).split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = f"{cur} {w}".strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]



def is_entity_like(node: JsonObj) -> bool:
    meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
    return (
        node.get("opClass") == "entity"
        or node.get("entityKind") in {"table", "entity"}
        or node.get("kind") == "entity"
        or isinstance(meta.get("columns"), list)
    )


def text_block(x: float, y: float, label: object, *, size: int = 12, anchor: str = "middle", color: str = "#0f172a", max_chars: int = 18) -> str:
    lines = wrap(label, max_chars)
    out = [f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="{size}" fill="{color}">']
    dy0 = -(len(lines) - 1) * 7
    for i, line in enumerate(lines):
        dy = dy0 + i * 14
        out.append(f'<tspan x="{x:.1f}" dy="{dy if i == 0 else 14:.1f}">{esc(line)}</tspan>')
    out.append('</text>')
    return "".join(out)


def node_shape(n: JsonObj, x: float, y: float, w: float, h: float, tokens: JsonObj) -> str:
    kind = n.get("kind", "node")
    label = n.get("label", n.get("id"))
    line = tokens["line"]
    fill = tokens["panel"]
    if kind in {"start", "end"}:
        return f'<circle cx="{x+w/2:.1f}" cy="{y+h/2:.1f}" r="{min(w,h)/2-4:.1f}" fill="{fill}" stroke="{line}" stroke-width="1.6"/>' + text_block(x+w/2, y+h/2+4, label, max_chars=12)
    if kind in {"decision", "gateway"}:
        pts = f'{x+w/2:.1f},{y:.1f} {x+w:.1f},{y+h/2:.1f} {x+w/2:.1f},{y+h:.1f} {x:.1f},{y+h/2:.1f}'
        return f'<polygon points="{pts}" fill="#fff7ed" stroke="{tokens["warn"]}" stroke-width="1.6"/>' + text_block(x+w/2, y+h/2+4, label, max_chars=12)
    if is_entity_like(n):
        cols = n.get("meta", {}).get("columns") or []
        body = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="10" fill="{fill}" stroke="{line}"/>',
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="30" rx="10" fill="{tokens["panel2"]}" stroke="{line}"/>',
                text_block(x+w/2, y+20, label, size=12, max_chars=16)]
        cy = y + 46
        for col in cols[:5]:
            name = col[0] if isinstance(col, list) and col else str(col)
            tag = col[1] if isinstance(col, list) and len(col) > 1 else ""
            body.append(f'<text x="{x+12:.1f}" y="{cy:.1f}" font-size="11" fill="{tokens["ink"]}">{esc(name)} <tspan fill="{tokens["muted"]}">{esc(tag)}</tspan></text>')
            cy += 16
        return "".join(body)
    fill = "#eef2ff" if kind in {"service", "module", "component"} else fill
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{tokens["radius"]}" fill="{fill}" stroke="{line}" stroke-width="1.4"/>' + text_block(x+w/2, y+h/2+4, label)


def arrow_defs(tokens: JsonObj) -> str:
    return f'''<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{tokens["line"]}"/></marker></defs>'''


def edge_line(a: tuple[float, float], b: tuple[float, float], label: str, tokens: JsonObj) -> str:
    x1, y1 = a; x2, y2 = b
    midx = (x1+x2)/2; midy = (y1+y2)/2 - 6
    lbl = f'<text x="{midx:.1f}" y="{midy:.1f}" text-anchor="middle" font-size="10" fill="{tokens["muted"]}">{esc(label)}</text>' if label else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{tokens["line"]}" stroke-width="1.4" marker-end="url(#arrow)"/>{lbl}'


def base_positions(dvm: JsonObj, layout: JsonObj | None = None) -> dict[str, JsonObj]:
    layout_nodes = (layout or {}).get("nodes", {}) if layout else {}
    if layout_nodes:
        return dict(layout_nodes)
    nodes = dvm.get("nodes", [])
    positions: dict[str, JsonObj] = {}
    for i, n in enumerate(nodes):
        positions[n["id"]] = {"x": 64 + (i % 4) * 190, "y": 96 + (i // 4) * 110, "w": 142, "h": 56}
    return positions


def render_generic(dvm: JsonObj, positions: dict[str, JsonObj], tokens: JsonObj) -> tuple[str, int, int]:
    parts: list[str] = []
    centers = {nid: (p["x"] + p["w"]/2, p["y"] + p["h"]/2) for nid, p in positions.items()}
    for e in dvm.get("edges", []):
        if e["source"] in centers and e["target"] in centers:
            parts.append(edge_line(centers[e["source"]], centers[e["target"]], e.get("label", ""), tokens))
    for n in dvm.get("nodes", []):
        p = positions[n["id"]]
        parts.append(node_shape(n, p["x"], p["y"], p["w"], p["h"], tokens))
    max_x = max((p["x"] + p["w"] for p in positions.values()), default=800) + 72
    max_y = max((p["y"] + p["h"] for p in positions.values()), default=420) + 72
    return "".join(parts), int(max_x), int(max_y)


def render_sequence(dvm: JsonObj, tokens: JsonObj) -> tuple[str, int, int]:
    nodes = dvm.get("nodes", [])
    edges = dvm.get("edges", [])
    width = max(780, 160 * len(nodes) + 80)
    height = max(360, 90 + 46 * len(edges) + 80)
    xmap = {n["id"]: 80 + i * 160 for i, n in enumerate(nodes)}
    parts: list[str] = []
    for n in nodes:
        x = xmap[n["id"]]
        parts.append(f'<rect x="{x-58}" y="70" width="116" height="42" rx="12" fill="{tokens["panel"]}" stroke="{tokens["line"]}"/>')
        parts.append(text_block(x, 96, n.get("label", n["id"]), max_chars=14))
        parts.append(f'<line x1="{x}" y1="112" x2="{x}" y2="{height-60}" stroke="{tokens["muted"]}" stroke-dasharray="5 6"/>')
    for i, e in enumerate(edges):
        y = 150 + i * 44
        sx = xmap.get(e["source"], 80); tx = xmap.get(e["target"], sx)
        if sx == tx:
            parts.append(f'<path d="M {sx} {y} C {sx+70} {y} {sx+70} {y+28} {sx} {y+28}" fill="none" stroke="{tokens["line"]}" marker-end="url(#arrow)"/>')
        else:
            parts.append(edge_line((sx, y), (tx, y), e.get("label", ""), tokens))
    return "".join(parts), width, height


def render_swimlane(dvm: JsonObj, tokens: JsonObj) -> tuple[str, int, int]:
    groups = dvm.get("groups", []) or [{"id":"lane", "label":"Lane"}]
    nodes = dvm.get("nodes", [])
    edges = dvm.get("edges", [])
    lane_h = 108
    width = 980
    height = 110 + lane_h * len(groups)
    y_by_group = {g["id"]: 86 + i * lane_h for i, g in enumerate(groups)}
    lane_nodes: dict[str, list[JsonObj]] = {g["id"]: [] for g in groups}
    for n in nodes:
        lane_nodes.setdefault(n.get("group") or n.get("lane") or groups[0]["id"], []).append(n)
    parts: list[str] = []
    pos: dict[str, JsonObj] = {}
    for i, g in enumerate(groups):
        y = 70 + i * lane_h
        parts.append(f'<rect x="38" y="{y}" width="900" height="{lane_h-10}" rx="12" fill="{tokens["panel"]}" stroke="#cbd5e1"/>')
        parts.append(f'<text x="60" y="{y+28}" font-size="13" font-weight="700" fill="{tokens["muted"]}">{esc(g.get("label", g["id"]))}</text>')
        for j, n in enumerate(lane_nodes.get(g["id"], [])):
            pos[n["id"]] = {"x": 210 + j * 170, "y": y + 26, "w": 130, "h": 50}
    centers = {nid: (p["x"]+p["w"]/2, p["y"]+p["h"]/2) for nid,p in pos.items()}
    for e in edges:
        if e["source"] in centers and e["target"] in centers:
            parts.append(edge_line(centers[e["source"]], centers[e["target"]], e.get("label", ""), tokens))
    for n in nodes:
        if n["id"] in pos:
            p=pos[n["id"]]; parts.append(node_shape(n,p["x"],p["y"],p["w"],p["h"],tokens))
    return "".join(parts), width, height


def render_timeline(dvm: JsonObj, tokens: JsonObj) -> tuple[str, int, int]:
    nodes = dvm.get("nodes", [])
    width = max(760, 120*len(nodes)+120); height=280
    y=150; parts=[f'<line x1="70" y1="{y}" x2="{width-70}" y2="{y}" stroke="{tokens["line"]}" stroke-width="2"/>']
    for i,n in enumerate(nodes):
        x=80+i*((width-160)/max(1,len(nodes)-1))
        parts.append(f'<circle cx="{x:.1f}" cy="{y}" r="10" fill="{tokens["accent"]}"/>')
        parts.append(text_block(x, y-32, n.get("meta",{}).get("when", n.get("order", i)), size=11, color=tokens["muted"], max_chars=10))
        parts.append(text_block(x, y+42, n.get("label", n["id"]), size=12, max_chars=14))
    return "".join(parts), width, height


def render_gantt(dvm: JsonObj, tokens: JsonObj) -> tuple[str, int, int]:
    groups = dvm.get("groups", [])
    tasks = dvm.get("nodes", [])
    max_end = max((int(t.get("end", 1)) for t in tasks), default=8)
    width = 880; lane_h=78; height=105+lane_h*max(1,len(groups))
    chart_x=190; unit=(width-chart_x-60)/max_end
    parts=[f'<line x1="{chart_x}" y1="58" x2="{width-50}" y2="58" stroke="#cbd5e1"/>']
    for t in range(max_end+1):
        x=chart_x+t*unit
        parts.append(f'<text x="{x:.1f}" y="50" font-size="10" fill="{tokens["muted"]}" text-anchor="middle">{t}</text>')
        parts.append(f'<line x1="{x:.1f}" y1="62" x2="{x:.1f}" y2="{height-35}" stroke="#e2e8f0"/>')
    y_by_lane={g["id"]:78+i*lane_h for i,g in enumerate(groups)}
    for g in groups:
        y=y_by_lane[g["id"]]
        parts.append(f'<text x="48" y="{y+30}" font-size="13" font-weight="700" fill="{tokens["muted"]}">{esc(g.get("label", g["id"]))}</text>')
    for task in tasks:
        y=y_by_lane.get(task.get("lane") or task.get("group"), 78)+8
        x=chart_x+int(task.get("start",0))*unit
        w=max(16,(int(task.get("end",1))-int(task.get("start",0)))*unit)
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="36" rx="10" fill="#dbeafe" stroke="{tokens["accent"]}"/>')
        parts.append(text_block(x+w/2, y+23, task.get("label", task["id"]), size=11, max_chars=18))
    return "".join(parts), width, height


def render_mindmap(dvm: JsonObj, tokens: JsonObj) -> tuple[str, int, int]:
    nodes=dvm.get("nodes",[]); edges=dvm.get("edges",[])
    width=860; height=540; cx=width/2; cy=height/2
    root=next((n for n in nodes if n.get("kind") == "root"), nodes[0] if nodes else {"id":"root","label":"root"})
    pos={root["id"]:{"x":cx-70,"y":cy-32,"w":140,"h":64}}
    branches=[n for n in nodes if n["id"]!=root["id"]]
    for i,n in enumerate(branches):
        ang=2*math.pi*i/max(1,len(branches))
        pos[n["id"]]={"x":cx+260*math.cos(ang)-65,"y":cy+180*math.sin(ang)-26,"w":130,"h":52}
    return render_generic(dvm,pos,tokens)



def _venn_palette(tokens: JsonObj) -> list[str]:
    return [tokens["accent"], tokens["success"], tokens["warn"], tokens["danger"]]


def _member_key(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(sorted(str(x) for x in value))
    if isinstance(value, str) and value:
        return tuple(sorted(part.strip() for part in value.split("+") if part.strip()))
    return tuple()


def render_venn(dvm: JsonObj, tokens: JsonObj) -> tuple[str, int, int]:
    """Render a small, deterministic 2/3-set Venn fixture.

    Contract:
      - groups with kind=set define the sets.
      - nodes with kind=region and meta.members define labeled regions.
      - this is an adapter fixture/example, not core semantics.
    """
    sets = [g for g in dvm.get("groups", []) if g.get("kind") == "set"] or dvm.get("groups", [])
    nodes = dvm.get("nodes", [])
    set_ids = [str(g["id"]) for g in sets[:3]]
    if not set_ids:
        # Keep the renderer total: a Venn with no sets becomes an empty panel, not a crash.
        return '<text x="60" y="120" font-size="13" fill="#64748b">No sets declared.</text>', 760, 260

    width, height = 860, 620
    # 2 and 3 set layouts are deliberately hard-coded for deterministic visual tests.
    if len(set_ids) == 1:
        circle = {set_ids[0]: (430.0, 290.0, 210.0, 145.0)}
        region_pos = {(set_ids[0],): (430.0, 290.0)}
    elif len(set_ids) == 2:
        a, b = set_ids[:2]
        circle = {a: (360.0, 285.0, 210.0, 145.0), b: (500.0, 285.0, 210.0, 145.0)}
        region_pos = {(a,): (300.0, 285.0), (b,): (560.0, 285.0), tuple(sorted((a, b))): (430.0, 285.0)}
    else:
        a, b, c = set_ids[:3]
        circle = {
            a: (330.0, 235.0, 190.0, 135.0),
            b: (530.0, 235.0, 190.0, 135.0),
            c: (430.0, 365.0, 190.0, 135.0),
        }
        region_pos = {
            (a,): (265.0, 220.0),
            (b,): (595.0, 220.0),
            (c,): (430.0, 455.0),
            tuple(sorted((a, b))): (430.0, 205.0),
            tuple(sorted((a, c))): (350.0, 335.0),
            tuple(sorted((b, c))): (510.0, 335.0),
            tuple(sorted((a, b, c))): (430.0, 292.0),
        }

    parts: list[str] = []
    palette = _venn_palette(tokens)
    parts.append('<g data-diagram-kind="venn">')
    for i, g in enumerate(sets[:3]):
        sid = str(g["id"])
        cx, cy, rx, ry = circle[sid]
        color = palette[i % len(palette)]
        parts.append(
            f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
            f'fill="{color}" fill-opacity="0.23" stroke="{color}" stroke-width="2.2"/>'
        )
        label_y = cy - ry - 14 if i < 2 else cy + ry + 28
        parts.append(text_block(cx, label_y, g.get("label", sid), size=14, color=tokens["ink"], max_chars=18))
    # Region labels are rendered as small pills so the semantic regions are reviewable.
    for n in nodes:
        members = _member_key((n.get("meta") or {}).get("members"))
        if not members:
            continue
        x, y = region_pos.get(members, (430.0, 505.0))
        label = n.get("label", n.get("id"))
        parts.append(
            f'<rect x="{x-72:.1f}" y="{y-18:.1f}" width="144" height="36" rx="12" '
            f'fill="{tokens["panel"]}" fill-opacity="0.88" stroke="#cbd5e1"/>'
        )
        parts.append(text_block(x, y+4, label, size=11, max_chars=20))
    note = dvm.get("diagram", {}).get("meta", {}).get("note", "set overlap view generated from JSONL")
    parts.append(f'<text x="46" y="{height-34}" font-size="11" fill="{tokens["muted"]}">{esc(note)}</text>')
    parts.append('</g>')
    return "".join(parts), width, height

def render_svg(dvm: JsonObj, *, layout: JsonObj | None = None, design_tokens: JsonObj | None = None, events_sha256: str = "") -> str:
    tokens = {**DEFAULT_TOKENS, **(design_tokens or {})}
    kind = dvm.get("diagram", {}).get("kind", "diagram")
    if kind == "sequence":
        body, width, height = render_sequence(dvm, tokens)
    elif kind == "swimlane":
        body, width, height = render_swimlane(dvm, tokens)
    elif kind == "timeline":
        body, width, height = render_timeline(dvm, tokens)
    elif kind == "gantt":
        body, width, height = render_gantt(dvm, tokens)
    elif kind == "mindmap":
        body, width, height = render_mindmap(dvm, tokens)
    elif kind == "venn":
        body, width, height = render_venn(dvm, tokens)
    else:
        positions = base_positions(dvm, layout)
        body, width, height = render_generic(dvm, positions, tokens)
    title = dvm.get("diagram", {}).get("label", dvm.get("diagram", {}).get("id", "diagram"))
    metadata = {
        "schema": "SvgProvenance.v1",
        "generatedFrom": "jsonl",
        "authority": "events.jsonl",
        "eventsSha256": events_sha256,
        "dvmSha256": sha256_text(canonical_json(dvm)),
        "diagramId": dvm.get("diagram", {}).get("id", "diagram"),
        "diagramKind": kind,
        "nodeIds": [str(n.get("id")) for n in dvm.get("nodes", [])],
        "edgeIds": [str(e.get("id")) for e in dvm.get("edges", [])],
        "groupIds": [str(g.get("id")) for g in dvm.get("groups", [])],
    }
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" data-generated-from="jsonl" data-authority="events.jsonl">
{arrow_defs(tokens)}
<metadata id="jsonl-diagram-provenance">{esc(json.dumps(metadata, ensure_ascii=False, sort_keys=True))}</metadata>
<rect width="100%" height="100%" fill="{tokens["bg"]}"/>
<text x="38" y="36" font-size="20" font-weight="800" fill="{tokens["ink"]}">{esc(title)}</text>
<text x="38" y="58" font-size="11" fill="{tokens["muted"]}">generated from JSONL · artifact is not authority</text>
{body}
</svg>
'''
