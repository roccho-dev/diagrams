from __future__ import annotations

from typing import Any

from jsonl_diagram_core.mxgraph_projection import render_image_drawio

JsonObj = dict[str, Any]


def render_drawio_native(model_xml: str, *, layout: JsonObj | None = None, events_sha256: str = "") -> str:
    del layout, events_sha256
    return model_xml


def render_drawio_image_exact(svg_text: str, *, diagram_id: str) -> str:
    # Keep the established image-exact projection API. This output is an image
    # projection, never a semantic current-state model.
    from jsonl_diagram_core.drawio_image_mode import wrap_svg_as_drawio_image
    return wrap_svg_as_drawio_image(svg_text, diagram_id=diagram_id)
