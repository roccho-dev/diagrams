from __future__ import annotations
import base64
from html import escape

def wrap_svg_as_drawio_image(svg: str, *, diagram_id: str = "diagram", width: int = 1200, height: int = 800) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    data = "data:image/svg+xml;base64," + encoded
    style = "shape=image;html=1;imageAspect=0;image=" + data
    return f'<mxfile host="app.diagrams.net"><diagram id="{escape(diagram_id)}" name="Page-1"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="svg-image" value="" style="{escape(style)}" vertex="1" parent="1"><mxGeometry x="0" y="0" width="{width}" height="{height}" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'
