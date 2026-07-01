from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

from examples.adapters.svg_renderer import base_positions
from jsonl_diagram_core.io import canonical_json, sha256_text

JsonObj = dict[str, Any]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _id(raw: object, *, prefix: str) -> str:
    value = str(raw)
    stem = re.sub(r'[^A-Za-z0-9_\-]', '_', value).strip('_') or 'id'
    if stem[0].isdigit():
        stem = f'n_{stem}'
    return f'{prefix}_{stem[:40]}__{hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]}'


def _geom(x: float, y: float, w: float, h: float) -> str:
    return f'<mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" as="geometry"/>'


def _node_style(kind: str) -> str:
    if kind in {'start', 'end'}:
        return 'ellipse;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#334155;strokeWidth=1.6;'
    if kind in {'decision', 'gateway'}:
        return 'rhombus;whiteSpace=wrap;html=1;fillColor=#fff7ed;strokeColor=#f59e0b;strokeWidth=1.6;'
    if kind in {'service', 'module', 'component'}:
        return 'rounded=1;whiteSpace=wrap;html=1;fillColor=#eef2ff;strokeColor=#334155;strokeWidth=1.4;arcSize=14;'
    if kind in {'region'}:
        return 'rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;fillOpacity=88;strokeColor=#cbd5e1;arcSize=12;'
    return 'rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#334155;strokeWidth=1.4;arcSize=14;'


def _cell_node(n: JsonObj, x: float, y: float, w: float, h: float) -> str:
    cid = _id(n['id'], prefix='node')
    value = esc(n.get('label', n['id']))
    style = _node_style(str(n.get('kind', 'node')))
    return f'<mxCell id="{cid}" value="{value}" style="{style}" vertex="1" parent="1" jsonlType="node" jsonlId="{esc(n["id"])}">{_geom(x,y,w,h)}</mxCell>'


def _cell_group(g: JsonObj, x: float, y: float, w: float, h: float, *, style: str | None = None) -> str:
    cid = _id(g['id'], prefix='group')
    value = esc(g.get('label', g['id']))
    style = style or 'rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#cbd5e1;arcSize=12;fontStyle=1;align=left;verticalAlign=top;spacingLeft=12;spacingTop=8;'
    return f'<mxCell id="{cid}" value="{value}" style="{style}" vertex="1" parent="1" jsonlType="group" jsonlId="{esc(g["id"])}">{_geom(x,y,w,h)}</mxCell>'


def _edge_cell(e: JsonObj, source_map: dict[str, str], *, points: tuple[tuple[float, float], tuple[float, float]] | None = None) -> str:
    cid = _id(e['id'], prefix='edge')
    value = esc(e.get('label', ''))
    style = 'endArrow=block;html=1;rounded=0;strokeColor=#334155;strokeWidth=1.4;'
    if e.get('kind') in {'return', 'fix'}:
        style += 'dashed=1;dashPattern=8 6;'
    if e.get('source') in source_map and e.get('target') in source_map:
        return f'<mxCell id="{cid}" value="{value}" style="{style}" edge="1" parent="1" source="{source_map[e["source"]]}" target="{source_map[e["target"]]}" jsonlType="edge" jsonlId="{esc(e["id"])}"><mxGeometry relative="1" as="geometry"/></mxCell>'
    if points:
        (x1, y1), (x2, y2) = points
        return f'<mxCell id="{cid}" value="{value}" style="{style}" edge="1" parent="1" jsonlType="edge" jsonlId="{esc(e["id"])}"><mxGeometry relative="1" as="geometry"><mxPoint x="{x1:.1f}" y="{y1:.1f}" as="sourcePoint"/><mxPoint x="{x2:.1f}" y="{y2:.1f}" as="targetPoint"/></mxGeometry></mxCell>'
    raise ValueError(f'edge lacks source target mapping: {e.get("id")}')


def _generic_positions(dvm: JsonObj, layout: JsonObj | None) -> dict[str, JsonObj]:
    return base_positions(dvm, layout)


def _timeline_positions(dvm: JsonObj) -> tuple[int, int, dict[str, JsonObj]]:
    nodes = dvm.get('nodes', [])
    width = max(760, 120 * len(nodes) + 120)
    height = 280
    y = 126
    positions: dict[str, JsonObj] = {}
    for i, n in enumerate(nodes):
        x = 80 + i * ((width - 160) / max(1, len(nodes) - 1))
        positions[n['id']] = {'x': x - 55, 'y': y - 24, 'w': 110, 'h': 48}
    return width, height, positions


def _sequence_positions(dvm: JsonObj) -> tuple[int, int, dict[str, JsonObj]]:
    nodes = dvm.get('nodes', [])
    edges = dvm.get('edges', [])
    width = max(780, 160 * len(nodes) + 80)
    height = max(360, 90 + 46 * len(edges) + 80)
    positions = {n['id']: {'x': 80 + i * 160 - 58, 'y': 70, 'w': 116, 'h': 42} for i, n in enumerate(nodes)}
    return width, height, positions


def _swimlane_cells(dvm: JsonObj) -> tuple[int, int, list[str], dict[str, str]]:
    groups = dvm.get('groups', []) or [{'id': 'lane', 'label': 'Lane'}]
    nodes = dvm.get('nodes', [])
    lane_h = 108
    width = 980
    height = 110 + lane_h * len(groups)
    cells: list[str] = []
    node_map: dict[str, str] = {}
    lane_nodes: dict[str, list[JsonObj]] = {g['id']: [] for g in groups}
    for n in nodes:
        lane_nodes.setdefault(n.get('group') or n.get('lane') or groups[0]['id'], []).append(n)
    for i, g in enumerate(groups):
        y = 70 + i * lane_h
        cells.append(_cell_group(g, 38, y, 900, lane_h - 10))
        for j, n in enumerate(lane_nodes.get(g['id'], [])):
            x = 210 + j * 170
            y2 = y + 26
            cells.append(_cell_node(n, x, y2, 130, 50))
            node_map[n['id']] = _id(n['id'], prefix='node')
    return width, height, cells, node_map


def _venn_cells(dvm: JsonObj) -> tuple[int, int, list[str], dict[str, str]]:
    groups = [g for g in dvm.get('groups', []) if g.get('kind') == 'set'] or dvm.get('groups', [])
    nodes = dvm.get('nodes', [])
    width, height = 860, 620
    set_ids = [str(g['id']) for g in groups[:3]]
    cells: list[str] = []
    node_map: dict[str, str] = {}
    if len(set_ids) >= 3:
        a, b, c = set_ids[:3]
        circles = {a: (140, 100, 380, 270), b: (340, 100, 380, 270), c: (240, 230, 380, 270)}
        region_pos = {
            (a,): (193, 202), (b,): (523, 202), (c,): (358, 437),
            tuple(sorted((a, b))): (358, 187), tuple(sorted((a, c))): (278, 317), tuple(sorted((b, c))): (438, 317), tuple(sorted((a, b, c))): (358, 274),
        }
    else:
        circles = {sid: (220 + i * 150, 150, 320, 230) for i, sid in enumerate(set_ids)}
        region_pos = {(sid,): (330 + i * 150, 270) for i, sid in enumerate(set_ids)}
    palette = ['#2563eb', '#16a34a', '#f59e0b']
    for i, g in enumerate(groups[:3]):
        x, y, w, h = circles[str(g['id'])]
        style = f'ellipse;whiteSpace=wrap;html=1;fillColor={palette[i % len(palette)]};fillOpacity=23;strokeColor={palette[i % len(palette)]};strokeWidth=2.2;'
        cells.append(_cell_group(g, x, y, w, h, style=style))
    def members(n: JsonObj) -> tuple[str, ...]:
        raw = (n.get('meta') or {}).get('members') or []
        return tuple(sorted(str(x) for x in raw))
    for n in nodes:
        x, y = region_pos.get(members(n), (358, 500))
        cells.append(_cell_node(n, x, y, 144, 36))
        node_map[n['id']] = _id(n['id'], prefix='node')
    return width, height, cells, node_map


def _positions_for_kind(dvm: JsonObj, layout: JsonObj | None) -> tuple[int, int, dict[str, JsonObj]]:
    kind = dvm.get('diagram', {}).get('kind', 'diagram')
    if kind == 'sequence':
        return _sequence_positions(dvm)
    if kind == 'timeline':
        return _timeline_positions(dvm)
    if kind == 'mindmap':
        # Native draw.io can route editable cells even if this uses a generic radial approximation.
        nodes = dvm.get('nodes', [])
        width, height = 860, 540
        cx, cy = width / 2, height / 2
        root = next((n for n in nodes if n.get('kind') == 'root'), nodes[0] if nodes else {'id': 'root'})
        pos = {root['id']: {'x': cx - 70, 'y': cy - 32, 'w': 140, 'h': 64}}
        branches = [n for n in nodes if n['id'] != root['id']]
        import math
        for i, n in enumerate(branches):
            ang = 2 * math.pi * i / max(1, len(branches))
            pos[n['id']] = {'x': cx + 260 * math.cos(ang) - 65, 'y': cy + 180 * math.sin(ang) - 26, 'w': 130, 'h': 52}
        return width, height, pos
    positions = _generic_positions(dvm, layout)
    width = int(max((p['x'] + p['w'] for p in positions.values()), default=800) + 72)
    height = int(max((p['y'] + p['h'] for p in positions.values()), default=420) + 72)
    return width, height, positions


def render_drawio_native(dvm: JsonObj, *, layout: JsonObj | None = None, events_sha256: str = '') -> str:
    diagram = dvm.get('diagram', {})
    kind = diagram.get('kind', 'diagram')
    cells: list[str] = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    title = esc(diagram.get('label', diagram.get('id', 'diagram')))
    cells.append(f'<mxCell id="title" value="{title}" style="text;html=1;strokeColor=none;fillColor=none;align=left;fontSize=20;fontStyle=1;fontColor=#0f172a;" vertex="1" parent="1" jsonlType="title">{_geom(38,24,680,32)}</mxCell>')
    if kind == 'swimlane':
        width, height, node_cells, node_map = _swimlane_cells(dvm)
        cells.extend(node_cells)
    elif kind == 'venn':
        width, height, node_cells, node_map = _venn_cells(dvm)
        cells.extend(node_cells)
    elif kind == 'gantt':
        # Gantt remains editable as task bars in native draw.io.
        groups = dvm.get('groups', [])
        tasks = dvm.get('nodes', [])
        max_end = max((int(t.get('end', 1)) for t in tasks), default=8)
        width, lane_h, height = 880, 78, 105 + 78 * max(1, len(groups))
        chart_x = 190
        unit = (width - chart_x - 60) / max_end
        node_map = {}
        for i, g in enumerate(groups):
            cells.append(_cell_group(g, 38, 66 + i * lane_h, width - 76, lane_h - 10))
        lane_y = {g['id']: 82 + i * lane_h for i, g in enumerate(groups)}
        for t in tasks:
            y = lane_y.get(t.get('lane') or t.get('group'), 82)
            x = chart_x + int(t.get('start', 0)) * unit
            w = max(28, (int(t.get('end', 1)) - int(t.get('start', 0))) * unit)
            cells.append(_cell_node(t, x, y, w, 30))
            node_map[t['id']] = _id(t['id'], prefix='node')
    else:
        width, height, positions = _positions_for_kind(dvm, layout)
        node_map = {}
        for n in dvm.get('nodes', []):
            p = positions[n['id']]
            cells.append(_cell_node(n, float(p['x']), float(p['y']), float(p['w']), float(p['h'])))
            node_map[n['id']] = _id(n['id'], prefix='node')
    for e in dvm.get('edges', []):
        cells.append(_edge_cell(e, node_map))
    provenance = esc(json.dumps({
        'schema': 'DrawioProvenance.v1',
        'generatedFrom': 'jsonl',
        'authority': 'events.jsonl',
        'eventsSha256': events_sha256,
        'dvmSha256': sha256_text(canonical_json(dvm)),
        'diagramId': diagram.get('id', 'diagram'),
        'diagramKind': kind,
        'nodeIds': [n['id'] for n in dvm.get('nodes', [])],
        'edgeIds': [e['id'] for e in dvm.get('edges', [])],
        'groupIds': [g['id'] for g in dvm.get('groups', [])],
    }, ensure_ascii=False, sort_keys=True))
    cells.append(f'<mxCell id="jsonl_provenance" value="{provenance}" style="text;html=1;strokeColor=none;fillColor=none;opacity=0;" vertex="1" parent="1" jsonlType="provenance">{_geom(0,0,1,1)}</mxCell>')
    body = ''.join(cells)
    return f'<mxfile host="app.diagrams.net" agent="jsonl-diagram" version="quality-gate"><diagram id="{esc(diagram.get("id", "diagram"))}" name="Page-1"><mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{width}" pageHeight="{height}" math="0" shadow="0"><root>{body}</root></mxGraphModel></diagram></mxfile>'


def render_drawio_image_exact(svg_text: str, *, diagram_id: str = 'diagram') -> str:
    root = ET.fromstring(svg_text)
    width = root.attrib.get('width', '1200')
    height = root.attrib.get('height', '800')
    data = base64.b64encode(svg_text.encode('utf-8')).decode('ascii')
    style = f'shape=image;verticalLabelPosition=bottom;verticalAlign=top;imageAspect=0;aspect=fixed;image=data:image/svg+xml;base64,{data};'
    body = ''.join([
        '<mxCell id="0"/>',
        '<mxCell id="1" parent="0"/>',
        f'<mxCell id="svg_image_exact" value="" style="{esc(style)}" vertex="1" parent="1" jsonlType="imageExact">{_geom(0,0,float(str(width).replace("px", "")),float(str(height).replace("px", "")))}</mxCell>',
    ])
    return f'<mxfile host="app.diagrams.net" agent="jsonl-diagram" version="quality-gate"><diagram id="{esc(diagram_id)}-image-exact" name="SVG exact"><mxGraphModel pageWidth="{esc(width)}" pageHeight="{esc(height)}"><root>{body}</root></mxGraphModel></diagram></mxfile>'
