from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


class CompiledGraphViewerError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _verify_sha(path: Path, expected: str, label: str) -> bytes:
    data = path.read_bytes()
    actual = _sha256(data)
    if actual != expected:
        raise CompiledGraphViewerError(f"{label} digest mismatch: expected={expected} actual={actual}")
    return data


def _inspect_source(xml_bytes: bytes) -> dict[str, Any]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise CompiledGraphViewerError("invalid mxfile XML") from exc
    if root.tag.rsplit("}", 1)[-1] != "mxfile":
        raise CompiledGraphViewerError("mxfile root required")
    diagrams = [x for x in root if x.tag.rsplit("}", 1)[-1] == "diagram"]
    if not diagrams:
        raise CompiledGraphViewerError("at least one diagram page required")
    page_ids: list[str] = []
    semantic_ids: set[str] = set()
    thresholds: dict[str, dict[str, float]] = {}
    threshold_count = 0
    external_assets: list[str] = []
    for diagram in diagrams:
        page_id = diagram.get("id", "")
        if not page_id or page_id in page_ids:
            raise CompiledGraphViewerError("unique non-empty page IDs required")
        page_ids.append(page_id)
        for elem in diagram.iter():
            sid = elem.get("semanticId") or (elem.get("id") if elem.tag.rsplit("}", 1)[-1] in {"object", "UserObject"} else None)
            if sid:
                if sid in semantic_ids:
                    raise CompiledGraphViewerError(f"duplicate semanticId: {sid}")
                semantic_ids.add(sid)
            width = elem.get("minScreenWidthPx")
            height = elem.get("minScreenHeightPx")
            if width is not None or height is not None:
                for name, raw in (("minScreenWidthPx", width), ("minScreenHeightPx", height)):
                    if raw is not None:
                        try:
                            value = float(raw)
                        except ValueError as exc:
                            raise CompiledGraphViewerError(f"{name} must be numeric") from exc
                        if value < 0:
                            raise CompiledGraphViewerError(f"{name} must be non-negative")
                if not sid:
                    raise CompiledGraphViewerError("visibility threshold requires stable object id")
                thresholds[sid] = {
                    "minScreenWidthPx": float(width or 0),
                    "minScreenHeightPx": float(height or 0),
                }
                threshold_count += 1
            for key in ("image", "src"):
                value = elem.get(key, "")
                if value.startswith(("http://", "https://", "//")):
                    external_assets.append(value)
    if external_assets:
        raise CompiledGraphViewerError("external source assets are forbidden in v1")
    return {
        "pageIds": page_ids,
        "semanticSubjectCount": len(semantic_ids),
        "semanticSubjectIds": sorted(semantic_ids),
        "thresholdSubjectCount": threshold_count,
        "thresholds": thresholds,
    }


def _app_js(source_sha: str, thresholds: dict[str, dict[str, float]], semantic_ids: list[str]) -> str:
    return f"""'use strict';
window.__compiledViewerProof = {{status:'BOOTING', sourceSha256:'{source_sha}', consoleErrors:[], externalRequests:[]}};
window.__semanticThresholds={json.dumps(thresholds, sort_keys=True, separators=(',', ':'))};
window.__semanticSubjectIds={json.dumps(semantic_ids, sort_keys=True, separators=(',', ':'))};
window.MathJax={{}};
window.PROXY_URL=''; window.STYLE_PATH='.'; window.SHAPES_PATH='.'; window.STENCIL_PATH='.';
window.DRAW_MATH_URL=''; window.GRAPH_IMAGE_PATH='.'; window.mxImageBasePath='.'; window.mxBasePath='.';
window.DRAWIO_BASE_URL='.'; window.EXPORT_URL=''; window.PLANT_URL=''; window.VSD_CONVERT_URL='';
window.Editor = window.Editor || {{}};
window.onDrawioViewerLoad = function() {{
  GraphViewer.viewerInitialized = function(viewer) {{
    const graph = viewer.graph;
    const original = graph.isCellVisible.bind(graph);
    const model = graph.getModel();
    const threshold = function(cell, name) {{
      const id = cell ? cell.getId() : null;
      const entry = id ? window.__semanticThresholds[id] : null;
      return entry && entry[name] != null ? Number(entry[name]) : 0;
    }};
    const nativeVisible = function(cell) {{
      let current = cell;
      while (current) {{
        if (!original(current)) return false;
        current = model.getParent(current);
      }}
      return true;
    }};
    const visibleVertex = function(cell) {{
      if (!nativeVisible(cell)) return false;
      const geometry = model.getGeometry(cell);
      if (!geometry) return true;
      const scale = graph.view.scale || 1;
      return geometry.width * scale >= threshold(cell, 'minScreenWidthPx') &&
             geometry.height * scale >= threshold(cell, 'minScreenHeightPx');
    }};
    graph.isCellVisible = function(cell) {{
      if (!nativeVisible(cell)) return false;
      if (model.isEdge(cell)) {{
        const source = model.getTerminal(cell, true);
        const target = model.getTerminal(cell, false);
        return !!source && !!target && visibleVertex(source) && visibleVertex(target);
      }}
      return !model.isVertex(cell) || visibleVertex(cell);
    }};
    const subjectSet = new Set(window.__semanticSubjectIds);
    const semanticId = function(cell) {{
      const id = cell ? cell.getId() : null;
      return id && subjectSet.has(id) ? id : null;
    }};
    const snapshot = function() {{
      const cells = model.cells || {{}};
      const visible = [];
      const hidden = [];
      Object.keys(cells).sort().forEach(function(id) {{
        const cell = cells[id];
        const sid = semanticId(cell);
        if (!sid) return;
        (graph.isCellVisible(cell) ? visible : hidden).push(sid);
      }});
      return {{scale: graph.view.scale, visible: visible, hidden: hidden}};
    }};
    window.__compiledViewer = viewer;
    window.__setSemanticZoom = function(scale) {{
      graph.view.setScale(scale);
      graph.refresh();
      const state = snapshot();
      window.__compiledViewerProof.lastSnapshot = state;
      return state;
    }};
    graph.view.addListener(mxEvent.SCALE, function() {{ graph.refresh(); }});
    window.__compiledViewerProof.status='READY';
    window.__compiledViewerProof.officialGraphViewerInitialized=true;
    window.__compiledViewerProof.pageCount=viewer.diagrams.length || 1;
    window.__compiledViewerProof.initialSnapshot=snapshot();
  }};
  GraphViewer.processElements();
}};
"""


def build_compiled_graphviewer(
    source: Path,
    runtime: Path,
    license_path: Path,
    runtime_pin: Path,
    out_dir: Path,
) -> dict[str, Any]:
    pin = json.loads(runtime_pin.read_text(encoding="utf-8"))
    if pin.get("kind") != "drawioViewerRuntimePin.v1":
        raise CompiledGraphViewerError("invalid runtime pin kind")
    if pin.get("repository") != "jgraph/drawio":
        raise CompiledGraphViewerError("official jgraph/drawio runtime required")
    if pin.get("tag") in {None, "", "latest"}:
        raise CompiledGraphViewerError("immutable runtime tag required")
    if re.fullmatch(r"[0-9a-f]{40}", str(pin.get("commit", ""))) is None:
        raise CompiledGraphViewerError("exact runtime commit required")
    if pin.get("viewerPath") != "src/main/webapp/js/viewer-static.min.js":
        raise CompiledGraphViewerError("unexpected official viewer path")
    runtime_bytes = _verify_sha(runtime, pin["viewerSha256"], "viewer runtime")
    license_bytes = _verify_sha(license_path, pin["licenseSha256"], "viewer license")
    source_bytes = source.read_bytes()
    inspection = _inspect_source(source_bytes)
    source_sha = _sha256(source_bytes)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "viewer-static.min.js").write_bytes(runtime_bytes)
    (out_dir / "LICENSE.drawio").write_bytes(license_bytes)
    (out_dir / "source.drawio").write_bytes(source_bytes)
    (out_dir / "app.js").write_text(_app_js(source_sha, inspection["thresholds"], inspection["semanticSubjectIds"]), encoding="utf-8")

    config = {
        "highlight": "#0000ff",
        "nav": True,
        "resize": True,
        "toolbar": "zoom layers lightbox",
        "xml": source_bytes.decode("utf-8"),
    }
    data_attr = html.escape(json.dumps(config, ensure_ascii=False, separators=(",", ":")), quote=True)
    index = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'none'; worker-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'">
<title>Compiled GraphViewer</title><style>html,body,#viewer{{width:100%;height:100%;margin:0;overflow:hidden}}#viewer{{min-height:600px}}</style>
<script src="app.js"></script><script src="viewer-static.min.js"></script></head>
<body><div id="viewer" class="mxgraph" data-mxgraph="{data_attr}"></div></body></html>
"""
    (out_dir / "index.html").write_text(index, encoding="utf-8")

    manifest = {
        "kind": "compiledGraphViewerBundle.v1",
        "source": {"path": "source.drawio", "sha256": source_sha, **{k:v for k,v in inspection.items() if k != "thresholds"}},
        "runtime": pin,
        "files": {},
        "runtimeExternalRequestsAllowed": 0,
        "generatedIsAuthority": False,
        "visibilityPolicy": {"fields": ["minScreenWidthPx", "minScreenHeightPx"], "monotonic": True, "mutatesSource": False},
    }
    for path in sorted(out_dir.iterdir()):
        if path.name == "manifest.json":
            continue
        manifest["files"][path.name] = _sha256(path.read_bytes())
    (out_dir / "manifest.json").write_bytes(_canonical(manifest))
    return manifest
