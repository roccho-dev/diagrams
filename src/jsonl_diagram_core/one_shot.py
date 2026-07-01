from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .io import canonical_json, read_jsonl, sha256_text
from .tokenizer import tokenize_events
from .reducer import reduce_tokens
from .render_ast import render_ast
from .svg_render_ast import render_svg_from_ast
from .drawio_render_ast import render_drawio_from_ast

JsonObj = dict[str, Any]

def dvm_to_simple_render_ast(dvm: JsonObj) -> JsonObj:
    items: list[JsonObj] = []
    order = {n["id"]: i for i, n in enumerate(dvm.get("nodes", []))}
    for i, node in enumerate(dvm.get("nodes", [])):
        items.append({"id": node["id"], "type": "box", "x": 60 + i*160, "y": 100, "width": 110, "height": 48, "label": node.get("label", node["id"]), "z": 1})
    for i, edge in enumerate(dvm.get("edges", [])):
        items.append({"id": edge["id"], "type": "line", "source": edge["source"], "target": edge["target"], "label": edge.get("label", ""), "z": 2+i})
    return render_ast(dvm.get("diagram", {}).get("id", "diagram"), items, width=max(800, 240 + len(order)*160), height=320)

def compile_one_shot(events_path: str | Path, out_dir: str | Path) -> JsonObj:
    events_path = Path(events_path); out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    events = read_jsonl(events_path)
    dvm = reduce_tokens(tokenize_events(events))
    ast = dvm_to_simple_render_ast(dvm)
    svg = render_svg_from_ast(ast)
    drawio = render_drawio_from_ast(ast)
    (out / "diagram.compiled.svg").write_text(svg, encoding="utf-8")
    (out / "diagram.compiled.drawio").write_text(drawio, encoding="utf-8")
    report = {"schema":"OneShotCompileReport.v1", "source": str(events_path), "sourceSha256": sha256_text(canonical_json(events)), "dvmHash": dvm["hash"], "artifacts": {"svg": sha256_text(svg), "drawio": sha256_text(drawio)}}
    (out / "compile-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return report
