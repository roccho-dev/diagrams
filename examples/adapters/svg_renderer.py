from __future__ import annotations

from typing import Any

from jsonl_diagram_core.mxgraph_projection import render_svg as _render_svg

JsonObj = dict[str, Any]


def render_svg(model_xml: str, *, layout: JsonObj | None = None, design_tokens: JsonObj | None = None, events_sha256: str = "") -> str:
    # Layout and design tokens are retained as adapter-call compatibility only;
    # geometry and style are already native mxGraphModel state.
    del layout, design_tokens
    return _render_svg(model_xml, events_sha256=events_sha256 or None)
