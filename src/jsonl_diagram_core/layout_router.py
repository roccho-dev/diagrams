from __future__ import annotations
from dataclasses import dataclass
from typing import Any

JsonObj = dict[str, Any]

@dataclass(frozen=True)
class LayoutDecision:
    engine: str
    reason: str
    confidence: float
    fallback: str | None = None

ENGINE_BY_KIND: dict[str, LayoutDecision] = {
    "dag": LayoutDecision("elk.layered", "directed acyclic graph", 0.95, "graphviz.dot"),
    "dependency": LayoutDecision("elk.layered", "directed dependency graph", 0.95, "graphviz.dot"),
    "dense": LayoutDecision("elk.layered", "directed graph fixture", 0.75, "graphology.force"),
    "architecture": LayoutDecision("elk.layered.compound", "nested architecture boxes", 0.9, "d2.elk"),
    "flow": LayoutDecision("elk.layered", "simple flow graph", 0.8, "dagre"),
    "swimlane": LayoutDecision("grid.free", "lane/slot layout is surface-first", 0.9, "elk.layered.edge-helper"),
    "wireframe": LayoutDecision("grid.free", "UI regions need grid plus overlays", 0.9, "css.grid"),
    "venn": LayoutDecision("venn.set-overlap", "set overlap is not a graph layout", 0.95, None),
    "sequence": LayoutDecision("plantuml.sequence", "lifeline/time-axis layout", 0.95, "mermaid.sequence"),
    "network": LayoutDecision("graphology.project", "network needs projection before layout", 0.8, "elk.force"),
    "mindmap": LayoutDecision("d3.hierarchy", "tree/hierarchy data", 0.85, "elk.mrtree"),
}

def choose_layout_engine(diagram_kind: str, *, intent: JsonObj | None = None) -> LayoutDecision:
    meta = (intent or {}).get("meta") if isinstance(intent, dict) else None
    if isinstance(meta, dict) and isinstance(meta.get("engine"), str):
        return LayoutDecision(meta["engine"], "explicit intent", 1.0, None)
    return ENGINE_BY_KIND.get(diagram_kind, LayoutDecision("unsupported", f"no router rule for {diagram_kind}", 0.0, None))
