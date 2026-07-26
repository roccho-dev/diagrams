#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

ERROR_PATTERNS = (
    "Error loading file",
    "InvalidCharacterError",
    "invalid distance too far back",
    "URI malformed",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_r_url(url: str) -> bytes | None:
    if "#R" not in url:
        return None
    try:
        return urllib.parse.unquote_to_bytes(url.split("#R", 1)[1])
    except ValueError:
        return None


def _labels_visible(page: object) -> bool:
    body_text = page.locator("body").inner_text(timeout=10_000)
    if all(label in body_text for label in ("Parent", "Child")):
        return True
    return page.locator("svg text").filter(has_text=re.compile("Parent|Child")).count() >= 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url-file", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--viewer-dom", type=Path, required=True)
    parser.add_argument("--editor-screenshot", type=Path, required=True)
    parser.add_argument("--editor-dom", type=Path, required=True)
    args = parser.parse_args()

    url = args.url_file.read_text(encoding="utf-8").strip()
    source = args.source.read_bytes()
    source_digest = _sha256(source)
    result: dict[str, object] = {
        "schema": "diagram.workViewBrowserProof.v1",
        "status": "ERROR",
        "sourceModelSha256": source_digest,
        "hostedViewerOpened": False,
        "diagramLabelsVisible": False,
        "errorDialogAbsent": False,
        "editControlAvailable": False,
        "editorOpened": False,
        "editorDiagramLabelsVisible": False,
        "editorPayloadDigestMatched": False,
    }

    for path in (
        args.out,
        args.screenshot,
        args.viewer_dom,
        args.editor_screenshot,
        args.editor_dom,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            context.add_init_script(
                """
                (() => {
                  window.__workViewMessages = [];
                  window.addEventListener('message', (event) => {
                    let data;
                    try {
                      data = typeof event.data === 'string'
                        ? event.data
                        : JSON.stringify(event.data);
                    } catch (_) {
                      data = String(event.data);
                    }
                    window.__workViewMessages.push({origin: event.origin, data});
                  }, true);
                })();
                """
            )
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            result["httpStatus"] = response.status if response is not None else None
            page.wait_for_timeout(8_000)
            result["hostedViewerOpened"] = True

            body_text = page.locator("body").inner_text(timeout=10_000)
            result["bodyTextSample"] = body_text[:2000]
            present_errors = [pattern for pattern in ERROR_PATTERNS if pattern.lower() in body_text.lower()]
            result["presentErrors"] = present_errors
            result["errorDialogAbsent"] = not present_errors
            result["diagramLabelsVisible"] = _labels_visible(page)
            args.viewer_dom.write_text(page.content(), encoding="utf-8")

            page.mouse.move(720, 970)
            page.wait_for_timeout(1_000)
            edit_control = page.locator('span[title="Edit"]')
            result["editControlCount"] = edit_control.count()
            result["editControlAvailable"] = edit_control.count() > 0

            editor = None
            if edit_control.count() > 0:
                candidate = edit_control.last
                result["editControlVisible"] = candidate.is_visible()
                result["editControlBox"] = candidate.bounding_box()
                before_pages = list(context.pages)
                before_url = page.url
                candidate.click(force=True)

                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    new_pages = [candidate_page for candidate_page in context.pages if candidate_page not in before_pages]
                    if new_pages:
                        editor = new_pages[-1]
                        break
                    if page.url != before_url:
                        editor = page
                        break
                    page.wait_for_timeout(500)

            if editor is not None:
                editor.wait_for_load_state("domcontentloaded", timeout=90_000)
                editor.wait_for_timeout(8_000)
                result["editorOpened"] = True
                result["editorUrl"] = editor.url
                editor_text = editor.locator("body").inner_text(timeout=10_000)
                result["editorBodyTextSample"] = editor_text[:2000]
                result["editorDiagramLabelsVisible"] = _labels_visible(editor)
                payload = _decode_r_url(editor.url)
                if payload is not None:
                    result["editorUrlPayloadSha256"] = _sha256(payload)
                    result["editorPayloadDigestMatched"] = _sha256(payload) == source_digest

                messages = editor.evaluate("window.__workViewMessages || []")
                result["editorMessageCount"] = len(messages)
                result["editorMessages"] = [
                    {"origin": message.get("origin"), "dataSample": str(message.get("data", ""))[:500]}
                    for message in messages
                ]
                source_text = source.decode("utf-8")
                for message in messages:
                    data = str(message.get("data", ""))
                    candidates = [data]
                    try:
                        parsed = json.loads(data)
                    except (json.JSONDecodeError, TypeError):
                        parsed = None
                    if isinstance(parsed, dict):
                        candidates.extend(value for value in parsed.values() if isinstance(value, str))
                    for candidate_payload in candidates:
                        if candidate_payload == source_text:
                            result["editorPayloadSha256"] = _sha256(candidate_payload.encode("utf-8"))
                            result["editorPayloadDigestMatched"] = True
                            break
                    if result["editorPayloadDigestMatched"]:
                        break
                args.editor_dom.write_text(editor.content(), encoding="utf-8")
                editor.screenshot(path=str(args.editor_screenshot), full_page=True)
            else:
                result["editorOpenError"] = "no popup or same-page navigation"

            page.screenshot(path=str(args.screenshot), full_page=True)
            browser.close()

        required = (
            result["hostedViewerOpened"],
            result["diagramLabelsVisible"],
            result["errorDialogAbsent"],
            result["editControlAvailable"],
            result["editorOpened"],
            result["editorDiagramLabelsVisible"],
            result["editorPayloadDigestMatched"],
        )
        result["status"] = "PASS" if all(required) else "FAIL"
        result["claimCeiling"] = "PASS requires exact source bytes observed in the Editor input channel"
    except Exception as exc:
        result["status"] = "BLOCKED"
        result["error"] = f"{type(exc).__name__}: {exc}"

    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
