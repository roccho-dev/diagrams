#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

VIEWER_BASE = (
    "https://viewer.diagrams.net/"
    "?tags=%7B%7D"
    "&lightbox=1"
    "&highlight=0000ff"
    "&edit=_blank"
    "&layers=1"
    "&nav=1"
    "&dark=auto"
    "#R"
)


class WorkViewError(ValueError):
    pass


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _decode_page(diagram: ET.Element) -> ET.Element:
    children = list(diagram)
    if children:
        model = children[0]
        if _local_name(model.tag) != "mxGraphModel":
            raise WorkViewError(f"unexpected diagram child: {model.tag}")
        return model

    payload = (diagram.text or "").strip()
    if not payload:
        raise WorkViewError("diagram page has no model payload")

    try:
        compressed = base64.b64decode(payload, validate=True)
        encoded_xml = zlib.decompress(compressed, wbits=-15).decode("utf-8")
        xml_text = urllib.parse.unquote(encoded_xml)
        model = ET.fromstring(xml_text)
    except (ValueError, UnicodeDecodeError, zlib.error, ET.ParseError) as exc:
        raise WorkViewError("invalid compressed diagram payload") from exc

    if _local_name(model.tag) != "mxGraphModel":
        raise WorkViewError(f"unexpected decoded page root: {model.tag}")
    return model


def inspect_mxfile(xml_bytes: bytes) -> dict[str, object]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise WorkViewError("invalid XML") from exc

    if _local_name(root.tag) != "mxfile":
        raise WorkViewError(f"expected mxfile root, got {root.tag}")

    pages: list[dict[str, object]] = []
    page_ids: set[str] = set()
    for index, diagram in enumerate(root):
        if _local_name(diagram.tag) != "diagram":
            continue
        page_id = diagram.attrib.get("id", "")
        if not page_id:
            raise WorkViewError(f"page {index} has no id")
        if page_id in page_ids:
            raise WorkViewError(f"duplicate page id: {page_id}")
        page_ids.add(page_id)

        model = _decode_page(diagram)
        cells = [node for node in model.iter() if _local_name(node.tag) == "mxCell"]
        vertices = sum(node.attrib.get("vertex") == "1" for node in cells)
        edges = sum(node.attrib.get("edge") == "1" for node in cells)
        pages.append(
            {
                "id": page_id,
                "name": diagram.attrib.get("name", f"Page-{index + 1}"),
                "cellCount": len(cells),
                "vertexCount": vertices,
                "edgeCount": edges,
            }
        )

    if not pages:
        raise WorkViewError("mxfile has no diagram pages")

    return {
        "pageCount": len(pages),
        "vertexCount": sum(int(page["vertexCount"]) for page in pages),
        "edgeCount": sum(int(page["edgeCount"]) for page in pages),
        "pages": pages,
    }


def build_work_view(xml_bytes: bytes) -> tuple[str, dict[str, object]]:
    inspection = inspect_mxfile(xml_bytes)
    source_sha256 = hashlib.sha256(xml_bytes).hexdigest()
    fragment = urllib.parse.quote_from_bytes(xml_bytes, safe="")
    url = VIEWER_BASE + fragment

    restored = urllib.parse.unquote_to_bytes(url.split("#R", 1)[1])
    if restored != xml_bytes:
        raise WorkViewError("URL exact roundtrip mismatch")

    receipt = {
        "schema": "diagram.workViewProof.v1",
        "status": "LOCAL_CODEC_PASS",
        "claimCeiling": "Hosted rendering and Editor payload require browser proof",
        "generatedIsAuthority": False,
        "urlFormat": "viewer-r-outer-mxfile-v1",
        "sourceModelSha256": source_sha256,
        "urlSha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
        **inspection,
    }
    return url, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--url-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()

    url, receipt = build_work_view(args.input.read_bytes())
    args.url_out.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_out.parent.mkdir(parents=True, exist_ok=True)
    args.url_out.write_text(url + "\n", encoding="utf-8")
    args.receipt_out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
