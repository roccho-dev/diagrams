from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from jsonl_diagram_core.proof import sha256_file


def check_svg(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errs = []
    if 'data-generated-from="jsonl"' not in text:
        errs.append("missing data-generated-from=jsonl")
    if 'data-authority="events.jsonl"' not in text:
        errs.append("missing data-authority=events.jsonl")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return [f"invalid svg xml: {exc}"]
    meta_text = None
    for child in root:
        if child.tag.endswith("metadata") and child.attrib.get("id") == "jsonl-diagram-provenance":
            meta_text = child.text
            break
    if not meta_text:
        errs.append("missing jsonl-diagram-provenance metadata")
    else:
        try:
            meta = json.loads(meta_text)
        except Exception as exc:
            errs.append(f"invalid provenance json: {exc}")
            meta = {}
        if meta.get("generatedFrom") != "jsonl":
            errs.append("provenance.generatedFrom must be jsonl")
        if meta.get("authority") != "events.jsonl":
            errs.append("provenance.authority must be events.jsonl")
        if not isinstance(meta.get("eventsSha256"), str) or len(meta.get("eventsSha256", "")) != 64:
            errs.append("provenance.eventsSha256 must be sha256")
        if not isinstance(meta.get("dvmSha256"), str) or len(meta.get("dvmSha256", "")) != 64:
            errs.append("provenance.dvmSha256 must be sha256")
    proof = path.with_name("proof.json")
    if proof.exists():
        try:
            pdata = json.loads(proof.read_text(encoding="utf-8"))
        except Exception as exc:
            errs.append(f"invalid proof json: {exc}")
        else:
            if pdata.get("svgSha256") != sha256_file(path):
                errs.append("proof.svgSha256 does not match svg file")
            if pdata.get("generatedIsAuthority") is not False:
                errs.append("proof.generatedIsAuthority must be false")
    return errs


def main(argv=None):
    root = Path((argv or sys.argv)[1] if len(argv or sys.argv) > 1 else ".")
    svgs = list(root.rglob("*.svg"))
    errors = []
    for p in svgs:
        errs = check_svg(p)
        if errs:
            errors.append({"file": str(p), "errors": errs})
    report = {"ok": not errors, "svgCount": len(svgs), "errors": errors}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1

if __name__ == "__main__":
    raise SystemExit(main())
