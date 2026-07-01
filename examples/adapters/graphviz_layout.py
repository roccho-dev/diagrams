from __future__ import annotations

import shutil
import subprocess
from typing import Any
from .d2_adapter import build_id_map, d2_quote

JsonObj = dict[str, Any]


def compile_dot(dvm: JsonObj) -> str:
    nodes = dvm.get("nodes", [])
    id_map = build_id_map((n["id"] for n in nodes), prefix="n")
    lines = ["digraph G {", "  graph [rankdir=LR, splines=true, overlap=false];", "  node [shape=box];"]
    for n in nodes:
        lines.append(f"  {id_map[n['id']]} [label=\"{d2_quote(n.get('label', n['id']))}\"];")
    for e in dvm.get("edges", []):
        lines.append(f"  {id_map[e['source']]} -> {id_map[e['target']]};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def layout_graphviz(dvm: JsonObj) -> JsonObj:
    if not shutil.which("dot"):
        return {"engine": "graphviz", "available": False, "layoutOnly": True, "fallbackUsed": True, "nodes": {}, "edges": []}
    nodes_list = dvm.get("nodes", [])
    id_map = build_id_map((n["id"] for n in nodes_list), prefix="n")
    raw_by_adapter = {v: k for k, v in id_map.items()}
    dot = compile_dot(dvm)
    proc = subprocess.run(["dot", "-Tplain"], input=dot, text=True, capture_output=True, check=True)
    nodes: dict[str, JsonObj] = {}
    scale = 110.0
    min_x = min_y = 10**9
    raw_positions: dict[str, tuple[float, float, float, float]] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0] == "node":
            aid = parts[1]
            sid = raw_by_adapter.get(aid, aid)
            x, y, w, h = map(float, parts[2:6])
            raw_positions[sid] = (x * scale, y * scale, max(w * scale, 96), max(h * scale, 44))
            min_x = min(min_x, x * scale)
            min_y = min(min_y, y * scale)
    for sid, (x, y, w, h) in raw_positions.items():
        nodes[sid] = {"x": round(x - min_x + 48, 2), "y": round(y - min_y + 48, 2), "w": round(w, 2), "h": round(h, 2)}
    return {"engine": "graphviz", "available": True, "layoutOnly": True, "fallbackUsed": False, "nodes": nodes, "edges": []}
