from __future__ import annotations
from html import escape
from typing import Any
from .render_ast import validate_render_ast

JsonObj = dict[str, Any]

def _center(item: JsonObj) -> tuple[float, float]:
    return (float(item.get("x", 0)) + float(item.get("width", 0))/2, float(item.get("y", 0)) + float(item.get("height", 0))/2)

def render_svg_from_ast(ast: JsonObj) -> str:
    validate_render_ast(ast)
    by_id = {i["id"]: i for i in ast["items"]}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(ast.get("width",1200))}" height="{int(ast.get("height",800))}" viewBox="0 0 {int(ast.get("width",1200))} {int(ast.get("height",800))}">', '<rect width="100%" height="100%" fill="#ffffff"/>']
    for item in ast["items"]:
        typ = item["type"]
        if typ == "box":
            out.append(f'<rect id="{escape(item["id"])}" x="{item["x"]}" y="{item["y"]}" width="{item["width"]}" height="{item["height"]}" rx="10" fill="#ffffff" stroke="#64748b"/>')
        elif typ == "ellipse":
            cx, cy = _center(item)
            out.append(f'<ellipse id="{escape(item["id"])}" cx="{cx}" cy="{cy}" rx="{float(item["width"])/2}" ry="{float(item["height"])/2}" fill="#ffffff" stroke="#64748b"/>')
        elif typ == "text":
            out.append(f'<text id="{escape(item["id"])}" x="{item["x"]}" y="{item["y"]}" font-family="Arial" font-size="14">{escape(str(item.get("label", item["id"])))}</text>')
        elif typ in {"line", "polyline"}:
            if "source" in item:
                x1, y1 = _center(by_id[item["source"]]); x2, y2 = _center(by_id[item["target"]])
                out.append(f'<line id="{escape(item["id"])}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#334155"/>')
            else:
                pts = " ".join(f'{p[0]},{p[1]}' for p in item["points"])
                out.append(f'<polyline id="{escape(item["id"])}" points="{escape(pts)}" fill="none" stroke="#334155"/>')
    out.append('</svg>')
    return "\n".join(out)
