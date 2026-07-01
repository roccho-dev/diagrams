from __future__ import annotations
from html import escape
from typing import Any
from .render_ast import validate_render_ast

JsonObj = dict[str, Any]

def _style(item: JsonObj) -> str:
    if item["type"] == "ellipse":
        return "ellipse;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#64748b;"
    if item["type"] == "text":
        return "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
    return "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#64748b;"

def render_drawio_from_ast(ast: JsonObj) -> str:
    validate_render_ast(ast)
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for item in ast["items"]:
        if item["type"] in {"box", "ellipse", "text", "image"}:
            value = escape(str(item.get("label", item.get("id", ""))))
            cells.append(f'<mxCell id="{escape(item["id"])}" value="{value}" style="{_style(item)}" vertex="1" parent="1"><mxGeometry x="{item["x"]}" y="{item["y"]}" width="{item["width"]}" height="{item["height"]}" as="geometry"/></mxCell>')
    for item in ast["items"]:
        if item["type"] in {"line", "polyline"}:
            if "source" in item:
                cells.append(f'<mxCell id="{escape(item["id"])}" value="{escape(str(item.get("label", "")))}" style="endArrow=block;html=1;rounded=0;strokeColor=#334155;" edge="1" parent="1" source="{escape(item["source"])}" target="{escape(item["target"])}"><mxGeometry relative="1" as="geometry"/></mxCell>')
            else:
                pts = item.get("points", [])
                src = pts[0] if pts else [0,0]; dst = pts[-1] if pts else [10,10]
                cells.append(f'<mxCell id="{escape(item["id"])}" style="endArrow=block;html=1;rounded=0;strokeColor=#334155;" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="{src[0]}" y="{src[1]}" as="sourcePoint"/><mxPoint x="{dst[0]}" y="{dst[1]}" as="targetPoint"/></mxGeometry></mxCell>')
    body = "".join(cells)
    return f'<mxfile host="app.diagrams.net"><diagram id="{escape(ast.get("diagramId", "diagram"))}" name="Page-1"><mxGraphModel><root>{body}</root></mxGraphModel></diagram></mxfile>'
