from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from . import model as _model

Json = dict[str, Any]


def _geometry_snapshot(cell: ET.Element) -> Json | None:
    """Include every geometry attribute and both direct and array points in visual hashes."""
    geometry = cell.find("mxGeometry")
    if geometry is None:
        return None
    out: Json = {"attributes": dict(sorted(geometry.attrib.items()))}
    direct_points = [
        dict(sorted(point.attrib.items()))
        for point in geometry.findall("./mxPoint")
    ]
    if direct_points:
        out["directPoints"] = direct_points
    arrays = []
    for array in geometry.findall("./Array"):
        arrays.append(
            {
                "attributes": dict(sorted(array.attrib.items())),
                "points": [
                    dict(sorted(point.attrib.items()))
                    for point in array.findall("mxPoint")
                ],
            }
        )
    if arrays:
        out["arrays"] = arrays
    return out


def _visual_material(xml_text: str) -> Json:
    values: list[Json] = []
    for z_index, cell in enumerate(_model._cells(xml_text)):
        if cell.get("jsonlType") not in {"group", "node", "edge"}:
            continue
        values.append(
            {
                "id": cell.get("jsonlId"),
                "parent": cell.get("parent"),
                "source": cell.get("source"),
                "target": cell.get("target"),
                "style": cell.get("style", ""),
                "locked": cell.get("locked") == "1",
                "geometry": _geometry_snapshot(cell) or {},
                "z": z_index,
            }
        )
    return {"cells": values}


# Proof-only compatibility patch. Canonical cutover must absorb these invariants
# into the sole production implementation and then delete this proof package.
_model._visual_material = _visual_material
