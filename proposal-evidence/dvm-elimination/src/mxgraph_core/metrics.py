from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from typing import Any

from .model import parse_model
from .project import absolute_bounds

Json = dict[str, Any]
Point = tuple[float, float]
Bounds = tuple[float, float, float, float]


def _cells(root: ET.Element) -> list[ET.Element]:
    return root.findall("./diagram/mxGraphModel/root//mxCell")


def _ancestor_ids(cell: ET.Element, by_cell_id: dict[str, ET.Element]) -> set[str]:
    values: set[str] = set()
    parent = cell.get("parent")
    while parent and parent not in {"0", "1"}:
        if parent in values:
            raise ValueError(f"parent cycle at {parent}")
        values.add(parent)
        parent_cell = by_cell_id.get(parent)
        if parent_cell is None:
            break
        parent = parent_cell.get("parent")
    return values


def _area(bounds: Bounds) -> float:
    return max(0.0, bounds[2]) * max(0.0, bounds[3])


def _rect_intersection(a: Bounds, b: Bounds) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    width = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    height = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    return width * height


def _circle_intersection(a: Bounds, b: Bounds) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if abs(aw - ah) > 1e-9 or abs(bw - bh) > 1e-9:
        raise ValueError("ellipse is not a circle")
    r1 = aw / 2.0
    r2 = bw / 2.0
    x1, y1 = ax + r1, ay + r1
    x2, y2 = bx + r2, by + r2
    d = math.hypot(x2 - x1, y2 - y1)
    if d >= r1 + r2:
        return 0.0
    if d <= abs(r1 - r2):
        return math.pi * min(r1, r2) ** 2
    alpha = math.acos((d * d + r1 * r1 - r2 * r2) / (2.0 * d * r1))
    beta = math.acos((d * d + r2 * r2 - r1 * r1) / (2.0 * d * r2))
    return r1 * r1 * alpha + r2 * r2 * beta - 0.5 * math.sqrt(
        (-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2)
    )


def _segments(points: list[Point]) -> list[tuple[Point, Point]]:
    return list(zip(points, points[1:]))


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, point: Point, *, eps: float = 1e-9) -> bool:
    return (
        min(a[0], b[0]) - eps <= point[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= point[1] <= max(a[1], b[1]) + eps
    )


def _segment_cross(a: Point, b: Point, c: Point, d: Point) -> bool:
    eps = 1e-9
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if (o1 > eps and o2 < -eps or o1 < -eps and o2 > eps) and (
        o3 > eps and o4 < -eps or o3 < -eps and o4 > eps
    ):
        return True
    if abs(o1) <= eps and _on_segment(a, b, c, eps=eps):
        return True
    if abs(o2) <= eps and _on_segment(a, b, d, eps=eps):
        return True
    if abs(o3) <= eps and _on_segment(c, d, a, eps=eps):
        return True
    if abs(o4) <= eps and _on_segment(c, d, b, eps=eps):
        return True
    return False


def _segment_rect_cross(a: Point, b: Point, rect: Bounds) -> bool:
    x, y, w, h = rect
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    if x <= a[0] <= x + w and y <= a[1] <= y + h:
        return True
    if x <= b[0] <= x + w and y <= b[1] <= y + h:
        return True
    return any(_segment_cross(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


def _xml_point(element: ET.Element | None) -> Point | None:
    if element is None or element.get("x") is None or element.get("y") is None:
        return None
    return float(element.get("x", "0")), float(element.get("y", "0"))


def _terminal_center(root: ET.Element, cell: ET.Element | None) -> Point | None:
    if cell is None:
        return None
    x, y, width, height = absolute_bounds(root, cell)
    return x + width / 2.0, y + height / 2.0


def _edge_path(root: ET.Element, edge: ET.Element, by_cell_id: dict[str, ET.Element]) -> Json:
    geometry = edge.find("mxGeometry")
    source_explicit = _xml_point(geometry.find("./mxPoint[@as='sourcePoint']") if geometry is not None else None)
    target_explicit = _xml_point(geometry.find("./mxPoint[@as='targetPoint']") if geometry is not None else None)
    source_inferred = _terminal_center(root, by_cell_id.get(edge.get("source", "")))
    target_inferred = _terminal_center(root, by_cell_id.get(edge.get("target", "")))

    source = source_explicit or source_inferred
    target = target_explicit or target_inferred
    points: list[Point] = []
    if source is not None:
        points.append(source)
    if geometry is not None:
        points.extend(
            (float(point.get("x", "0")), float(point.get("y", "0")))
            for point in geometry.findall("./Array[@as='points']/mxPoint")
        )
    if target is not None:
        points.append(target)

    resolved = source is not None and target is not None and len(points) >= 2
    explicit = source_explicit is not None and target_explicit is not None
    precision = "explicit" if explicit else "inferred"
    if explicit:
        method = "explicit-source-target-polyline"
    elif source_explicit is not None or target_explicit is not None:
        method = "mixed-explicit-terminal-center-estimate"
    elif resolved:
        method = "terminal-center-estimate"
    else:
        method = "unresolved"
    return {
        "edge": edge.get("jsonlId"),
        "precision": precision,
        "resolved": resolved,
        "method": method,
        "points": points,
    }


def _combined_precision(*records: Json) -> str:
    return "explicit" if records and all(record["precision"] == "explicit" for record in records) else "inferred"


def measure_model(xml_text: str, *, require_exact_edges: bool = False) -> Json:
    root = parse_model(xml_text)
    cells = _cells(root)
    by_cell_id = {cell.get("id", ""): cell for cell in cells}
    vertices = [cell for cell in cells if cell.get("jsonlType") in {"group", "node"}]
    edges = [cell for cell in cells if cell.get("jsonlType") == "edge"]
    bounds = {cell.get("id", ""): absolute_bounds(root, cell) for cell in vertices}

    overlap: list[Json] = []
    for index, left in enumerate(vertices):
        for right in vertices[index + 1 :]:
            left_id = left.get("id", "")
            right_id = right.get("id", "")
            if left_id in _ancestor_ids(right, by_cell_id) or right_id in _ancestor_ids(left, by_cell_id):
                continue
            a = bounds[left_id]
            b = bounds[right_id]
            left_circle = "ellipse" in left.get("style", "") and abs(a[2] - a[3]) < 1e-9
            right_circle = "ellipse" in right.get("style", "") and abs(b[2] - b[3]) < 1e-9
            if left_circle and right_circle:
                area = _circle_intersection(a, b)
                left_area = math.pi * (a[2] / 2.0) ** 2
                right_area = math.pi * (b[2] / 2.0) ** 2
                method = "circle-exact"
            else:
                area = _rect_intersection(a, b)
                left_area = _area(a)
                right_area = _area(b)
                method = "rectangle-or-bbox-exact"
            if area > 0:
                overlap.append(
                    {
                        "a": left.get("jsonlId"),
                        "b": right.get("jsonlId"),
                        "intersectionArea": area,
                        "aInB": area / left_area if left_area else 0.0,
                        "bInA": area / right_area if right_area else 0.0,
                        "method": method,
                    }
                )

    containment: list[Json] = []
    for cell in vertices:
        parent_id = cell.get("parent")
        if parent_id in by_cell_id and by_cell_id[parent_id].get("jsonlType") == "group":
            child_bounds = bounds[cell.get("id", "")]
            parent_bounds = bounds[parent_id]
            area = _rect_intersection(child_bounds, parent_bounds)
            child_area = _area(child_bounds)
            containment.append(
                {
                    "child": cell.get("jsonlId"),
                    "parent": by_cell_id[parent_id].get("jsonlId"),
                    "ratio": area / child_area if child_area else 0.0,
                    "method": "rectangle-bounds-exact",
                }
            )

    paths = {edge.get("id", ""): _edge_path(root, edge, by_cell_id) for edge in edges}
    edge_path_warnings: list[Json] = []
    edge_path_errors: list[Json] = []
    for edge in edges:
        record = paths[edge.get("id", "")]
        if not record["resolved"]:
            edge_path_errors.append(
                {
                    "edge": record["edge"],
                    "code": "edge_path_unresolved",
                    "precision": record["precision"],
                    "method": record["method"],
                }
            )
        elif record["precision"] == "inferred":
            finding = {
                "edge": record["edge"],
                "code": "edge_path_inferred",
                "precision": "inferred",
                "method": record["method"],
            }
            (edge_path_errors if require_exact_edges else edge_path_warnings).append(finding)

    edge_node_crossings: list[Json] = []
    for edge in edges:
        path = paths[edge.get("id", "")]
        if not path["resolved"]:
            continue
        source_id = edge.get("source")
        target_id = edge.get("target")
        source_cell = by_cell_id.get(source_id or "")
        target_cell = by_cell_id.get(target_id or "")
        ignored = {source_id, target_id}
        if source_cell is not None:
            ignored |= _ancestor_ids(source_cell, by_cell_id)
        if target_cell is not None:
            ignored |= _ancestor_ids(target_cell, by_cell_id)
        for vertex in vertices:
            if vertex.get("id") in ignored:
                continue
            rect = bounds[vertex.get("id", "")]
            if any(_segment_rect_cross(a, b, rect) for a, b in _segments(path["points"])):
                precision = path["precision"]
                edge_node_crossings.append(
                    {
                        "edge": edge.get("jsonlId"),
                        "node": vertex.get("jsonlId"),
                        "precision": precision,
                        "method": (
                            "explicit-segment-vs-rectangle-exact"
                            if precision == "explicit"
                            else "inferred-segment-vs-rectangle-advisory"
                        ),
                    }
                )

    edge_edge_crossings: list[Json] = []
    for index, left in enumerate(edges):
        for right in edges[index + 1 :]:
            if {left.get("source"), left.get("target")} & {right.get("source"), right.get("target")}:
                continue
            left_path = paths[left.get("id", "")]
            right_path = paths[right.get("id", "")]
            if not left_path["resolved"] or not right_path["resolved"]:
                continue
            if any(
                _segment_cross(a, b, c, d)
                for a, b in _segments(left_path["points"])
                for c, d in _segments(right_path["points"])
            ):
                precision = _combined_precision(left_path, right_path)
                edge_edge_crossings.append(
                    {
                        "a": left.get("jsonlId"),
                        "b": right.get("jsonlId"),
                        "precision": precision,
                        "method": "explicit-segment-exact" if precision == "explicit" else "inferred-segment-advisory",
                    }
                )

    precision_counts = {
        "explicit": sum(1 for record in paths.values() if record["precision"] == "explicit" and record["resolved"]),
        "inferred": sum(1 for record in paths.values() if record["precision"] == "inferred" and record["resolved"]),
        "rendered": 0,
        "unresolved": sum(1 for record in paths.values() if not record["resolved"]),
    }
    if edge_path_errors:
        status = "error"
    elif edge_path_warnings or edge_node_crossings or edge_edge_crossings:
        status = "warning"
    else:
        status = "pass"

    edge_path_rows = [
        {
            "edge": record["edge"],
            "precision": record["precision"],
            "resolved": record["resolved"],
            "method": record["method"],
            "pointCount": len(record["points"]),
        }
        for record in paths.values()
    ]
    return {
        "schema": "MxGraphGeometryMetrics.v2",
        "vertexCount": len(vertices),
        "edgeCount": len(edges),
        "overlaps": overlap,
        "containment": containment,
        "edgePaths": edge_path_rows,
        "edgePathPrecisionCounts": precision_counts,
        "edgePathWarnings": edge_path_warnings,
        "edgePathErrors": edge_path_errors,
        "edgeNodeCrossings": edge_node_crossings,
        "edgeEdgeCrossings": edge_edge_crossings,
        "requireExactEdges": require_exact_edges,
        "modelExact": not edge_path_warnings and not edge_path_errors,
        "status": status,
        "claimCeiling": (
            "Rectangle and equal-radius-circle geometry is model-exact. Edge crossing is exact only when both "
            "sourcePoint and targetPoint are explicit; terminal-center paths are inferred advisories. Rendered, "
            "curved, rotated-shape and text-perception claims require a fixed renderer."
        ),
    }
