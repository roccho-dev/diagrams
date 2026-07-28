from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from jsonl_diagram_core.mxgraph_projection import render_dot, semantic_snapshot

JsonObj = dict[str, Any]


def compile_dot(model_xml: str) -> str:
    return render_dot(model_xml)


def layout_graphviz(model_xml: str) -> JsonObj:
    dot = compile_dot(model_xml)
    executable = shutil.which("dot")
    snapshot = semantic_snapshot(model_xml)
    if executable is None:
        return {"engine": "graphviz.dot", "available": False, "layoutOnly": True, "fallbackUsed": True, "nodes": {}}
    proc = subprocess.run([executable, "-Tjson"], input=dot, text=True, capture_output=True)
    if proc.returncode != 0:
        return {"engine": "graphviz.dot", "available": False, "layoutOnly": True, "fallbackUsed": True, "error": proc.stderr, "nodes": {}}
    value = json.loads(proc.stdout)
    positions: dict[str, JsonObj] = {}
    for obj in value.get("objects", []):
        name = obj.get("name")
        pos = obj.get("pos")
        if isinstance(name, str) and isinstance(pos, str) and "," in pos:
            x, y = (float(part) for part in pos.split(",", 1))
            positions[name] = {"x": x, "y": y, "w": float(obj.get("width", 1)) * 72, "h": float(obj.get("height", 1)) * 72}
    return {"engine": "graphviz.dot", "available": True, "layoutOnly": True, "fallbackUsed": False, "nodes": positions, "modelNodeCount": len(snapshot["nodes"])}
