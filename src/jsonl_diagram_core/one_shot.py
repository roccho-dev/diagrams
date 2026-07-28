from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import read_jsonl, sha256_text
from .mxgraph_model import build_model
from .mxgraph_projection import render_svg

JsonObj = dict[str, Any]


def compile_one_shot(events_path: str | Path, out_dir: str | Path) -> JsonObj:
    events_path = Path(events_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    events = read_jsonl(events_path)
    model = build_model(events)
    svg = render_svg(model)
    (out / "diagram.compiled.drawio").write_text(model, encoding="utf-8")
    (out / "diagram.compiled.svg").write_text(svg, encoding="utf-8")
    report: JsonObj = {
        "schema": "OneShotCompileReport.v2",
        "source": str(events_path),
        "sourceSha256": sha256_text(events_path.read_text(encoding="utf-8")),
        "modelSha256": sha256_text(model),
        "artifacts": {"svg": sha256_text(svg), "drawio": sha256_text(model)},
        "authority": "events.jsonl",
        "generatedIsAuthority": False,
    }
    (out / "compile-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
