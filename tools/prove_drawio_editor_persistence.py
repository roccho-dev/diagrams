#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

DRAWIO_VERSION = "30.0.4"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_cdp(port: int, process: subprocess.Popen[bytes], timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    last: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"draw.io exited before CDP became ready: {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last = exc
        time.sleep(0.25)
    raise RuntimeError(f"CDP did not become ready at {url}: {last}")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse(path: Path) -> ET.Element:
    return ET.fromstring(path.read_text(encoding="utf-8"))


def entries(root: ET.Element) -> dict[str, tuple[ET.Element, dict[str, str]]]:
    result: dict[str, tuple[ET.Element, dict[str, str]]] = {}
    wrapped: set[int] = set()
    for obj in root.iter():
        if local(obj.tag) != "object":
            continue
        cell = next((child for child in list(obj) if local(child.tag) == "mxCell"), None)
        if cell is None:
            raise AssertionError("XML user object missing mxCell")
        wrapper_id = obj.attrib.get("id")
        nested_id = cell.attrib.get("id")
        if not wrapper_id:
            raise AssertionError("XML user object missing id")
        if nested_id and nested_id != wrapper_id:
            raise AssertionError(f"XML user object id mismatch: {wrapper_id} != {nested_id}")
        result[wrapper_id] = (cell, dict(obj.attrib))
        wrapped.add(id(cell))
    for cell in root.iter():
        if local(cell.tag) != "mxCell" or id(cell) in wrapped:
            continue
        cell_id = cell.attrib.get("id")
        if cell_id:
            result[cell_id] = (cell, {})
    return result


def find_objects(root: ET.Element, role: str) -> list[ET.Element]:
    return [element for element in root.iter() if local(element.tag) == "object" and element.attrib.get("role") == role]


def stable_object_attrs(item: ET.Element) -> dict[str, str]:
    return dict(sorted((key, value) for key, value in item.attrib.items() if key != "label"))


def semantic_snapshot(root: ET.Element) -> dict[str, Any]:
    cells = entries(root)
    semantic = find_objects(root, "semantic-node")
    scope_cell, scope_attrs = cells.get("scope", (ET.Element("missing"), {}))
    return {
        "cellIds": sorted(cells),
        "semanticObjects": [stable_object_attrs(item) for item in semantic],
        "scopeValue": scope_attrs.get("label", scope_cell.attrib.get("value")),
    }


def review_snapshot(root: ET.Element) -> dict[str, Any]:
    cells = entries(root)
    artifacts = find_objects(root, "diagram-artifact")
    overlays = find_objects(root, "decision-overlay")
    overlay_parents = sorted(
        cell.attrib.get("parent", "")
        for obj in overlays
        for cell in obj
        if local(cell.tag) == "mxCell"
    )
    scope_cell, scope_attrs = cells.get("scope", (ET.Element("missing"), {}))
    return {
        "cellIds": sorted(cells),
        "artifactObjects": [stable_object_attrs(item) for item in artifacts],
        "overlayObjects": [dict(sorted(item.attrib.items())) for item in overlays],
        "overlayParents": overlay_parents,
        "scopeValue": scope_attrs.get("label", scope_cell.attrib.get("value")),
    }


def page_diagnostics(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => ({
          title: document.title,
          url: location.href,
          bodyText: (document.body?.innerText || '').slice(0, 4000),
          visibleTextareas: Array.from(document.querySelectorAll('textarea')).filter(e => {
            const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden';
          }).map(e => ({className: e.className, value: e.value})),
          visibleEditables: Array.from(document.querySelectorAll('[contenteditable="true"]')).filter(e => {
            const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden';
          }).map(e => ({className: e.className, text: e.innerText})),
          globals: Object.keys(window).filter(k => /editor|graph|ui/i.test(k)).slice(0, 100)
        })"""
    )


def edit_and_save(page: Page, old: str, new: str, screenshot_dir: Path, stem: str) -> dict[str, Any]:
    page.wait_for_timeout(2500)
    page.screenshot(path=str(screenshot_dir / f"{stem}-opened.png"), full_page=True)
    locator = page.get_by_text(old, exact=True)
    count = locator.count()
    if count == 0:
        raise RuntimeError(f"visible label not found: {old!r}")
    locator.first.dblclick(force=True)
    page.wait_for_timeout(500)
    editors = page.locator("textarea.mxCellEditor:visible, textarea:visible, [contenteditable='true']:visible")
    editor_count = editors.count()
    if editor_count == 0:
        raise RuntimeError("no visible draw.io cell editor appeared after double-click")
    editor = editors.last
    editor.focus()
    page.keyboard.press("Control+A")
    page.keyboard.insert_text(new)
    page.keyboard.press("Control+Enter")
    page.wait_for_timeout(350)
    page.keyboard.press("Control+S")
    page.wait_for_timeout(1800)
    page.screenshot(path=str(screenshot_dir / f"{stem}-saved.png"), full_page=True)
    return {
        "labelMatchesBefore": count,
        "editorCount": editor_count,
        "diagnostics": page_diagnostics(page),
    }


def run_editor(app: Path, input_path: Path, old: str, new: str, out_dir: Path, stem: str) -> dict[str, Any]:
    port = free_port()
    profile = out_dir / f"profile-{stem}"
    log_path = out_dir / f"{stem}-drawio.log"
    command = [
        str(app),
        "--no-sandbox",
        "--disable-gpu",
        "--disable-update",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        str(input_path),
    ]
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "ELECTRON_DISABLE_SECURITY_WARNINGS": "true"})
        try:
            wait_cdp(port, process)
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                deadline = time.monotonic() + 30
                page: Page | None = None
                while time.monotonic() < deadline:
                    pages = [p for context in browser.contexts for p in context.pages]
                    candidates = [p for p in pages if p.url and not p.url.startswith("devtools://")]
                    if candidates:
                        page = candidates[-1]
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=1000)
                        except Exception:
                            pass
                        if page.get_by_text(old, exact=True).count() > 0:
                            break
                    time.sleep(0.25)
                if page is None:
                    raise RuntimeError("no draw.io renderer page was exposed over CDP")
                result = edit_and_save(page, old, new, out_dir, stem)
                browser.close()
                return {"command": command, "cdpPort": port, **result}
        except Exception:
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                    pages = [p for context in browser.contexts for p in context.pages]
                    diagnostics = [page_diagnostics(p) for p in pages]
                    (out_dir / f"{stem}-failure-diagnostics.json").write_text(
                        json.dumps(diagnostics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    for index, page in enumerate(pages):
                        page.screenshot(path=str(out_dir / f"{stem}-failure-{index}.png"), full_page=True)
                    browser.close()
            except Exception:
                pass
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drawio-app", type=Path, required=True)
    parser.add_argument("--semantic", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    semantic = args.out / "semantic-editor-proof.drawio"
    review = args.out / "review-editor-proof.drawio"
    shutil.copy2(args.semantic, semantic)
    shutil.copy2(args.review, review)
    semantic_before_root = parse(semantic)
    review_before_root = parse(review)
    semantic_before = semantic_snapshot(semantic_before_root)
    review_before = review_snapshot(review_before_root)
    if not semantic_before["semanticObjects"]:
        raise AssertionError("semantic fixture has no semantic user object")
    if not review_before["artifactObjects"] or not review_before["overlayObjects"]:
        raise AssertionError("review fixture has no artifact/overlay user objects")
    semantic_run = run_editor(args.drawio_app, semantic, "scope purpose", "scope purpose · saved", args.out, "semantic")
    semantic_after_root = parse(semantic)
    semantic_after = semantic_snapshot(semantic_after_root)
    if semantic_after["scopeValue"] != "scope purpose · saved":
        raise AssertionError(f"semantic edit did not persist: {semantic_after['scopeValue']!r}")
    if semantic_after["semanticObjects"] != semantic_before["semanticObjects"]:
        raise AssertionError("semantic XML user-object metadata changed during editor save")
    if semantic_after["cellIds"] != semantic_before["cellIds"]:
        raise AssertionError("semantic stable cell IDs changed during editor save")
    review_run = run_editor(args.drawio_app, review, "scope purpose", "scope purpose · review saved", args.out, "review")
    review_after_root = parse(review)
    review_after = review_snapshot(review_after_root)
    if review_after["scopeValue"] != "scope purpose · review saved":
        raise AssertionError(f"review edit did not persist: {review_after['scopeValue']!r}")
    if review_after["artifactObjects"] != review_before["artifactObjects"]:
        raise AssertionError("review artifact marker metadata changed during editor save")
    if review_after["overlayObjects"] != review_before["overlayObjects"]:
        raise AssertionError("decision overlay user-object metadata changed during editor save")
    if review_after["overlayParents"] != review_before["overlayParents"]:
        raise AssertionError("decision overlay layer ownership changed during editor save")
    if review_after["cellIds"] != review_before["cellIds"]:
        raise AssertionError("review stable cell IDs changed during editor save")
    from jsonl_diagram_core.decision_overlay import inspect_semantic_drawio
    from jsonl_diagram_core.quality import validate_drawio_quality
    rejected: dict[str, str] = {}
    for name, fn in {
        "semanticInspection": lambda: inspect_semantic_drawio(review.read_text(encoding="utf-8")),
        "qualityEntry": lambda: validate_drawio_quality(review.read_text(encoding="utf-8")),
    }.items():
        try:
            fn()
        except Exception as exc:
            rejected[name] = str(exc)
        else:
            raise AssertionError(f"saved review artifact was accepted by {name}")
    report = {
        "kind": "DrawioEditorPersistenceProof.v1",
        "status": "PASS",
        "drawioVersion": DRAWIO_VERSION,
        "semantic": {
            "beforeSha256": sha256(args.semantic),
            "savedSha256": sha256(semantic),
            "before": semantic_before,
            "after": semantic_after,
            "run": semantic_run,
        },
        "review": {
            "beforeSha256": sha256(args.review),
            "savedSha256": sha256(review),
            "before": review_before,
            "after": review_after,
            "run": review_run,
            "rejections": rejected,
        },
        "claimCeiling": {
            "metadataPersistence": True,
            "semanticUserObjectPersistence": True,
            "reviewMarkerPersistence": True,
            "overlayLayerPersistence": True,
            "actualUiEditAndSave": True,
            "renderExactAudit": False,
            "businessMeaningProven": False,
        },
    }
    (args.out / "editor-persistence-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.out / "PASS").write_text("PASS\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "drawioVersion": DRAWIO_VERSION}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
