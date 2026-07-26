#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ERROR_PATTERNS = (
    "Error loading file",
    "InvalidCharacterError",
    "invalid distance too far back",
    "URI malformed",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url-file", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
    args = parser.parse_args()

    url = args.url_file.read_text(encoding="utf-8").strip()
    result: dict[str, object] = {
        "schema": "diagram.workViewNegativeBrowserProof.v1",
        "status": "ERROR",
        "expectedFailure": "truncated Work View URL must not render the source diagram",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            response = page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(8_000)
            body_text = page.locator("body").inner_text(timeout=10_000)
            present_errors = [pattern for pattern in ERROR_PATTERNS if pattern.lower() in body_text.lower()]
            labels_visible = all(label in body_text for label in ("Parent", "Child"))
            result.update(
                {
                    "httpStatus": response.status if response is not None else None,
                    "bodyTextSample": body_text[:2000],
                    "presentErrors": present_errors,
                    "diagramLabelsVisible": labels_visible,
                }
            )
            page.screenshot(path=str(args.screenshot), full_page=True)
            browser.close()

        result["status"] = "PASS" if not labels_visible else "FAIL"
    except Exception as exc:
        result["status"] = "BLOCKED"
        result["error"] = f"{type(exc).__name__}: {exc}"

    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
