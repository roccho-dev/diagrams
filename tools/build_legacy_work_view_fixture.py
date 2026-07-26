#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import urllib.parse
import zlib
from pathlib import Path

from build_work_view import VIEWER_BASE, inspect_mxfile


def legacy_whole_file_deflate_url(xml_bytes: bytes) -> str:
    inspect_mxfile(xml_bytes)
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(xml_bytes) + compressor.flush()
    payload = base64.b64encode(compressed).decode("ascii")
    return VIEWER_BASE + urllib.parse.quote(payload, safe="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--url-out", type=Path, required=True)
    args = parser.parse_args()

    url = legacy_whole_file_deflate_url(args.input.read_bytes())
    args.url_out.parent.mkdir(parents=True, exist_ok=True)
    args.url_out.write_text(url + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
