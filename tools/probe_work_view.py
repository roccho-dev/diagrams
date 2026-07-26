#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url-file", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
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
        "editorPayloadDigestMatched": False,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
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

            labels_visible = all(label in body_text for label in ("Parent", "Child"))
            if not labels_visible:
                labels_visible = page.locator("svg text").filter(has_text=re.compile("Parent|Child")).count() >= 2
            result["diagramLabelsVisible"] = labels_visible

            edit_candidates = page.locator('a,button,[role="button"],*[title],*[aria-label]')
            edit_index: int | None = None
            candidate_count = edit_candidates.count()
            for index in range(candidate_count):
                element = edit_candidates.nth(index)
                signature = " ".join(
                    filter(
                        None,
                        [
                            element.get_attribute("title"),
                            element.get_attribute("aria-label"),
                            element.inner_text(timeout=1000).strip(),
                        ],
                    )
                )
                if re.search(r"\bedit\b", signature, re.IGNORECASE):
                    edit_index = index
                    break
            result["editControlAvailable"] = edit_index is not None

            if edit_index is not None:
                try:
                    with page.expect_popup(timeout=20_000) as popup_info:
                        edit_candidates.nth(edit_index).click()
                    editor = popup_info.value
                    editor.wait_for_load_state("domcontentloaded", timeout=90_000)
                    editor.wait_for_timeout(3_000)
                    result["editorOpened"] = True
                    result["editorUrl"] = editor.url
                    payload = _decode_r_url(editor.url)
                    if payload is not None:
                        result["editorPayloadSha256"] = _sha256(payload)
                        result["editorPayloadDigestMatched"] = _sha256(payload) == source_digest
                except PlaywrightTimeoutError:
                    result["editorOpenError"] = "popup timeout"

            page.screenshot(path=str(args.screenshot), full_page=True)
            browser.close()

        required = (
            result["hostedViewerOpened"],
            result["diagramLabelsVisible"],
            result["errorDialogAbsent"],
            result["editControlAvailable"],
        )
        result["status"] = "PASS" if all(required) else "FAIL"
    except Exception as exc:
        result["status"] = "BLOCKED"
        result["error"] = f"{type(exc).__name__}: {exc}"

    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
