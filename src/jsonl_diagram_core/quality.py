from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

JsonObj = dict[str, Any]
SVG_NS = "{http://www.w3.org/2000/svg}"


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def _positive_number(value: str | None) -> bool:
    if value is None:
        return False
    raw = str(value).strip().replace('px', '')
    try:
        return float(raw) > 0
    except ValueError:
        return False


def parse_svg_provenance(root: ET.Element) -> JsonObj:
    for el in root.iter():
        if _local(el.tag) == 'metadata' and el.attrib.get('id') == 'jsonl-diagram-provenance':
            text = ''.join(el.itertext()).strip()
            if not text:
                raise AssertionError('svg provenance metadata is empty')
            return json.loads(html.unescape(text))
    raise AssertionError('svg provenance metadata missing')


def validate_svg_quality(svg_text: str, *, expected_nodes: int | None = None, expected_edges: int | None = None, expected_groups: int | None = None) -> JsonObj:
    root = ET.fromstring(svg_text)
    if _local(root.tag) != 'svg':
        raise AssertionError('root is not svg')
    if not _positive_number(root.attrib.get('width')) or not _positive_number(root.attrib.get('height')):
        raise AssertionError('svg width/height must be positive')
    if root.attrib.get('data-generated-from') != 'jsonl':
        raise AssertionError('svg must declare data-generated-from=jsonl')
    if root.attrib.get('data-authority') != 'events.jsonl':
        raise AssertionError('svg must declare data-authority=events.jsonl')
    provenance = parse_svg_provenance(root)
    for key in ('schema', 'generatedFrom', 'authority', 'eventsSha256', 'dvmSha256'):
        if key not in provenance:
            raise AssertionError(f'svg provenance missing {key}')
    if provenance.get('schema') != 'SvgProvenance.v1':
        raise AssertionError('unexpected svg provenance schema')
    if not re.fullmatch(r'[0-9a-f]{64}', str(provenance.get('eventsSha256', ''))):
        raise AssertionError('eventsSha256 must be sha256 hex')
    if not re.fullmatch(r'[0-9a-f]{64}', str(provenance.get('dvmSha256', ''))):
        raise AssertionError('dvmSha256 must be sha256 hex')
    node_ids = provenance.get('nodeIds', [])
    edge_ids = provenance.get('edgeIds', [])
    group_ids = provenance.get('groupIds', [])
    if expected_nodes is not None and len(node_ids) != expected_nodes:
        raise AssertionError(f'svg nodeIds count mismatch: {len(node_ids)} != {expected_nodes}')
    if expected_edges is not None and len(edge_ids) != expected_edges:
        raise AssertionError(f'svg edgeIds count mismatch: {len(edge_ids)} != {expected_edges}')
    if expected_groups is not None and len(group_ids) != expected_groups:
        raise AssertionError(f'svg groupIds count mismatch: {len(group_ids)} != {expected_groups}')
    text = ''.join(root.itertext()).strip()
    if len(text) < 8:
        raise AssertionError('svg text content is unexpectedly small')
    visible_shapes = [el for el in root.iter() if _local(el.tag) in {'rect', 'circle', 'ellipse', 'polygon', 'path', 'line', 'polyline', 'text'}]
    if len(visible_shapes) < max(1, (expected_nodes or 1)):
        raise AssertionError('svg has too few visible elements')
    return {
        'schema': 'SvgQualityResult.v1',
        'width': root.attrib.get('width'),
        'height': root.attrib.get('height'),
        'nodeCount': len(node_ids),
        'edgeCount': len(edge_ids),
        'groupCount': len(group_ids),
        'visibleElementCount': len(visible_shapes),
        'eventsSha256': provenance.get('eventsSha256'),
        'dvmSha256': provenance.get('dvmSha256'),
    }


def validate_drawio_quality(drawio_text: str, *, expected_nodes: int | None = None, expected_edges: int | None = None, mode: str = 'native') -> JsonObj:
    root = ET.fromstring(drawio_text)
    if root.tag != 'mxfile':
        raise AssertionError('drawio root must be mxfile')
    cells = list(root.iter('mxCell'))
    by_id: dict[str, ET.Element] = {}
    for cell in cells:
        cid = cell.attrib.get('id')
        if not cid:
            raise AssertionError('mxCell missing id')
        if cid in by_id:
            raise AssertionError(f'duplicate mxCell id: {cid}')
        by_id[cid] = cell
    if '0' not in by_id or '1' not in by_id:
        raise AssertionError('drawio root/layer cells 0 and 1 are required')
    if 'parent' in by_id['0'].attrib:
        raise AssertionError('mxCell id=0 must not have parent')
    if by_id['1'].attrib.get('parent') != '0':
        raise AssertionError('mxCell id=1 must be parented by 0')
    vertex_ids = {cid for cid, cell in by_id.items() if cell.attrib.get('vertex') == '1'}
    edge_cells = [cell for cell in cells if cell.attrib.get('edge') == '1']
    for cell in cells:
        if cell.attrib.get('vertex') == '1':
            geom = cell.find('mxGeometry')
            if geom is None:
                raise AssertionError(f'vertex {cell.attrib.get("id")} missing mxGeometry')
            if not _positive_number(geom.attrib.get('width')) or not _positive_number(geom.attrib.get('height')):
                raise AssertionError(f'vertex {cell.attrib.get("id")} must have positive geometry')
        if cell.attrib.get('edge') == '1':
            source = cell.attrib.get('source')
            target = cell.attrib.get('target')
            geom = cell.find('mxGeometry')
            has_points = geom is not None and (geom.find('mxPoint') is not None or list(geom.iter('mxPoint')))
            if source or target:
                if source not in vertex_ids or target not in vertex_ids:
                    raise AssertionError(f'edge {cell.attrib.get("id")} source/target must reference vertices')
            elif not has_points:
                raise AssertionError(f'edge {cell.attrib.get("id")} needs source/target or points')
    native_nodes = [c for c in cells if c.attrib.get('jsonlType') == 'node']
    native_edges = [c for c in cells if c.attrib.get('jsonlType') == 'edge']
    if mode == 'native':
        if expected_nodes is not None and len(native_nodes) != expected_nodes:
            raise AssertionError(f'drawio node count mismatch: {len(native_nodes)} != {expected_nodes}')
        if expected_edges is not None and len(native_edges) != expected_edges:
            raise AssertionError(f'drawio edge count mismatch: {len(native_edges)} != {expected_edges}')
    if mode == 'image':
        image_cells = [c for c in cells if c.attrib.get('jsonlType') == 'imageExact']
        if len(image_cells) != 1:
            raise AssertionError('image mode drawio must have exactly one jsonlType=imageExact cell')
        if 'image=data:image/svg+xml' not in image_cells[0].attrib.get('style', ''):
            raise AssertionError('image mode drawio must embed SVG data URI')
    return {
        'schema': 'DrawioQualityResult.v1',
        'mode': mode,
        'cellCount': len(cells),
        'vertexCount': len(vertex_ids),
        'edgeCount': len(edge_cells),
        'jsonlNodeCount': len(native_nodes),
        'jsonlEdgeCount': len(native_edges),
    }
