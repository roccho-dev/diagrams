#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def duplicate_state_paths(root: Path) -> list[str]:
    patterns = ("dvm.json", "comparison-ir", "semantic-state.json", "render-state", "rendering-ir", "render_ast.py", "drawio_render_ast.py")
    result: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(root).as_posix().lower()
        if any(pattern in relative for pattern in patterns):
            result.append(path.relative_to(root).as_posix())
    return sorted(result)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--semantic-receipt", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    policy = load(args.policy)
    runtime = load(args.runtime)
    semantic_receipt = load(args.semantic_receipt)
    source_path = args.bundle / "source.drawio"
    source_bytes = source_path.read_bytes()
    source_sha = sha256(source_bytes)
    if source_sha != policy["source"]["mxfileSha256"]:
        raise ValueError("source digest mismatch")

    index = (args.bundle / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<div id="viewer" class="mxgraph" data-mxgraph="([^"]*)"></div>', index)
    if match is None:
        raise ValueError("compiled viewer payload missing")
    payload = html.unescape(match.group(1))
    external_requests: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(args.browser))
        page = browser.new_page(
            viewport={"width": runtime["viewport"]["width"], "height": runtime["viewport"]["height"]},
            device_scale_factor=runtime["viewport"]["devicePixelRatio"],
            color_scheme=runtime["theme"],
            reduced_motion="reduce",
        )
        page.on("request", lambda request: external_requests.append(request.url) if request.url.startswith(("http://", "https://")) else None)
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.set_content(
            '<style>html,body,#viewer{width:100%;height:100%;margin:0;background:#fff}#viewer{min-height:600px}</style>'
            '<div id="viewer" class="mxgraph" data-mxgraph="' + html.escape(payload, quote=True) + '"></div>'
        )
        page.add_script_tag(content=(args.bundle / "app.js").read_text(encoding="utf-8"))
        page.add_script_tag(content=(args.bundle / "viewer-static.min.js").read_text(encoding="utf-8"))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if page.evaluate("Boolean(window.__compiledViewerProof && window.__compiledViewerProof.status === 'READY')"):
                break
            page.wait_for_timeout(100)
        else:
            raise RuntimeError("official GraphViewer did not reach READY")

        observation = page.evaluate(
            """
            () => {
              const graph = window.__compiledViewer.graph;
              const model = graph.getModel();
              const stable = value => JSON.stringify(value);
              const snapshot = () => Object.keys(model.cells || {}).sort().map(id => {
                const cell = model.getCell(id); const g = cell && cell.geometry;
                return {id, value: cell && cell.value, style: cell && cell.style,
                  parent: cell && cell.parent && cell.parent.id, source: cell && cell.source && cell.source.id,
                  target: cell && cell.target && cell.target.id,
                  geometry: g ? [g.x,g.y,g.width,g.height,g.relative === true] : null};
              });
              const before = stable(snapshot());
              const cellMap = {scope:'group_scope', input:'node_input', output:'node_output'};
              const subjects = {};
              const usableColor = value => Boolean(value && value !== 'none' && value !== 'transparent' && !value.includes('light-dark(') && !value.includes('rgba(0, 0, 0, 0)'));
              const computedColor = (node, property, fallback) => {
                if (!node) return fallback;
                const selector = property === 'fill'
                  ? 'rect,ellipse,polygon,path[fill]:not([fill="none"])'
                  : 'div,span,text,tspan';
                const target = (node.matches && node.matches(selector) ? node : null) || (node.querySelector && node.querySelector(selector)) || node;
                const styleValue = getComputedStyle(target)[property];
                if (usableColor(styleValue)) return styleValue;
                const attributeValue = target.getAttribute && target.getAttribute(property);
                if (usableColor(attributeValue)) return attributeValue;
                return fallback;
              };
              const rectOf = node => {
                if (!node || !node.getBoundingClientRect) return null;
                const r=node.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height};
              };
              const containsRect = (outer,inner) => outer && inner && inner.x >= outer.x && inner.y >= outer.y && inner.x+inner.width <= outer.x+outer.width && inner.y+inner.height <= outer.y+outer.height;
              const opaque = node => {
                if (!node) return false; const style=getComputedStyle(node); const opacity=parseFloat(style.opacity || '1');
                const fill=computedColor(node,'fill','transparent').toLowerCase();
                return opacity >= .99 && fill !== 'none' && fill !== 'transparent' && !fill.includes('rgba(0, 0, 0, 0)');
              };
              const allPainted = Object.keys(model.cells || {}).map(id => graph.view.getState(model.getCell(id))).filter(state => state && state.shape && state.shape.node);
              const fullyOccluded = node => {
                const target=rectOf(node); if (!target || target.width <= 0 || target.height <= 0) return false;
                return allPainted.some(state => {
                  const candidate=state.shape.node; if (!candidate || candidate === node || node.contains(candidate) || candidate.contains(node)) return false;
                  const follows=Boolean(node.compareDocumentPosition(candidate) & Node.DOCUMENT_POSITION_FOLLOWING);
                  return follows && opaque(candidate) && containsRect(rectOf(candidate),target);
                });
              };
              for (const [semanticId,cellId] of Object.entries(cellMap)) {
                const cell = model.getCell(cellId); const state = graph.view.getState(cell);
                if (!state) { subjects[semanticId] = {present:false}; continue; }
                const label = state.text && state.text.boundingBox;
                const fill = state.style && state.style.fillColor && state.style.fillColor !== 'none' ? state.style.fillColor : '#ffffff';
                subjects[semanticId] = {
                  present:true, exactness:'renderer-exact',
                  bounds:[state.x,state.y,state.width,state.height],
                  labelBounds: label ? [label.x,label.y,label.width,label.height] : [state.x,state.y,0,0],
                  clipBounds:[state.x,state.y,state.width,state.height],
                  labelOcclusionFraction: fullyOccluded(state.text && state.text.node) ? 1 : 0,
                  subjectOcclusionFraction: fullyOccluded(state.shape && state.shape.node) ? 1 : 0,
                  textColor: computedColor(state.text && state.text.node,'color',state.style && state.style.fontColor || '#000000'),
                  backgroundColor: computedColor(state.shape && state.shape.node,'fill',fill)
                };
              }
              const edgeCell = model.getCell('edge_flow'); const edgeState = graph.view.getState(edgeCell);
              const edges = {flow: edgeState ? {present:true,exactness:'renderer-exact',source:'input',target:'output',points:edgeState.absolutePoints.map(p=>[p.x,p.y])}:{present:false}};
              graph.refresh();
              const after = stable(snapshot());
              return {subjects, edges, before, after, svgCount:document.querySelectorAll('#viewer svg').length,
                initialized:window.__compiledViewerProof.officialGraphViewerInitialized === true};
            }
            """
        )
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(args.screenshot), full_page=True, animations="disabled")
        browser.close()

    screenshot_bytes = args.screenshot.read_bytes()
    comparison = semantic_receipt.get("comparison", {})
    output = {
        "kind": "diagram.renderObservations.v1",
        "sourceMxfileSha256": source_sha,
        "semanticDigest": policy["source"]["semanticDigest"],
        "semanticStatus": comparison.get("status"),
        "pageIds": policy["source"]["pageIds"],
        "initialized": observation["initialized"],
        "svgCount": observation["svgCount"],
        "sourceModelUnchanged": observation["before"] == observation["after"] and sha256(source_path.read_bytes()) == source_sha,
        "externalRequests": sorted(set(external_requests)),
        "consoleErrors": console_errors,
        "pageErrors": page_errors,
        "unsupported": [],
        "duplicateRenderStatePaths": duplicate_state_paths(args.repo_root),
        "subjects": observation["subjects"],
        "edges": observation["edges"],
        "screenshot": {"sha256": sha256(screenshot_bytes), "byteLength": len(screenshot_bytes), "nonEmpty": len(screenshot_bytes) > 0},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(canonical(output) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
