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


def _edit_candidates(page: object) -> list[dict[str, object]]:
    locator = page.locator('a,button,[role="button"]')
    candidates: list[dict[str, object]] = []
    for index in range(locator.count()):
        element = locator.nth(index)
        try:
            if not element.is_visible():
                continue
            title = element.get_attribute("title") or ""
            aria = element.get_attribute("aria-label") or ""
            text = element.inner_text(timeout=1000).strip()
            signature = " ".join(part for part in (title, aria, text) if part)
            if re.search(r"\bedit\b", signature, re.IGNORECASE):
                candidates.append(
                    {
                        "index": index,
                        "tag": element.evaluate("el => el.tagName"),
                        "title": title,
                        "ariaLabel": aria,
                        "text": text,
                        "href": element.get_attribute("href"),
                        "target": element.get_attribute("target"),
                    }
                )
        except Exception:
            continue
    return candidates


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

            candidates = _edit_candidates(page)
            result["editCandidates"] = candidates
            result["editControlAvailable"] = bool(candidates)

            editor = None
            if candidates:
                raw_locator = page.locator('a,button,[role="button"]')
                candidate = raw_locator.nth(int(candidates[0]["index"]))
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

                if editor is None:
                    href = candidates[0].get("href")
                    if isinstance(href, str) and href and not href.lower().startswith("javascript:"):
                        editor = context.new_page()
                        editor.goto(urllib.parse.urljoin(page.url, href), wait_until="domcontentloaded", timeout=90_000)

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
                    result["editorPayloadSha256"] = _sha256(payload)
                    result["editorPayloadDigestMatched"] = _sha256(payload) == source_digest
                args.editor_dom.write_text(editor.content(), encoding="utf-8")
                editor.screenshot(path=str(args.editor_screenshot), full_page=True)
            else:
                result["editorOpenError"] = "no popup, navigation, or direct href"

            page.screenshot(path=str(args.screenshot), full_page=True)
            browser.close()

        required = (
            result["hostedViewerOpened"],
            result["diagramLabelsVisible"],
            result["errorDialogAbsent"],
            result["editControlAvailable"],
            result["editorOpened"],
            result["editorDiagramLabelsVisible"],
        )
        result["status"] = "PASS" if all(required) else "FAIL"
        result["claimCeiling"] = (
            "Editor source labels proven; exact source bytes proven only when editorPayloadDigestMatched=true"
        )
    except Exception as exc:
        result["status"] = "BLOCKED"
        result["error"] = f"{type(exc).__name__}: {exc}"

    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
