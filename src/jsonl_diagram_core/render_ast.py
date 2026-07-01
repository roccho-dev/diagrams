from __future__ import annotations
from typing import Any

JsonObj = dict[str, Any]
NODE_SHAPES = {"box", "ellipse", "text", "image"}
EDGE_SHAPES = {"line", "polyline"}

def render_ast(diagram_id: str, items: list[JsonObj], *, width: int = 1200, height: int = 800) -> JsonObj:
    ast = {"schema":"RenderAst.v1", "diagramId": diagram_id, "width": width, "height": height, "items": sorted(items, key=lambda x: (int(x.get("z", 0)), x.get("id", "")))}
    validate_render_ast(ast)
    return ast

def validate_render_ast(ast: JsonObj) -> None:
    ids: set[str] = set()
    for item in ast.get("items", []):
        typ = item.get("type")
        iid = item.get("id")
        if not isinstance(iid, str) or not iid:
            raise ValueError("render item id must be non-empty")
        if iid in ids:
            raise ValueError(f"duplicate render item id: {iid}")
        ids.add(iid)
        if typ not in NODE_SHAPES | EDGE_SHAPES:
            raise ValueError(f"unsupported render item type: {typ}")
        if typ in NODE_SHAPES:
            for key in ("x", "y", "width", "height"):
                if key not in item:
                    raise ValueError(f"{iid} missing {key}")
        if typ in EDGE_SHAPES and not (("source" in item and "target" in item) or "points" in item):
            raise ValueError(f"{iid} edge requires source/target or points")
