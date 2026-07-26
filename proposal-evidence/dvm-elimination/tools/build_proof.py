#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from mxgraph_core import (
    build_model,
    measure_model,
    render_d2,
    render_dot,
    render_image_drawio,
    render_svg,
    render_text,
    semantic_hash,
    visual_hash,
)
from mxgraph_core.fixtures import fixtures
from verify_required_evidence import verify_required_evidence

FORBIDDEN = re.compile(r"\bDVM\b|DiagramViewModel|\bRenderAst\b|\bRenderingIR\b")
INDEPENDENT_ARTIFACTS = {"dvm.json", "rendering-ir.json", "semantic-state.json"}
VOLATILE = {
    "validation/local-preflight.json",
    "validation/final-local-preflight-audit.json",
    "validation/final-local-preflight-audit.md",
    "validation/twin-replay.json",
    "validation/zip-replay.json",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return sha256(text.encode("utf-8"))


def clear(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def viewer_url(xml: bytes) -> str:
    ET.fromstring(xml)
    component = urllib.parse.quote(xml.decode("utf-8"), safe="-_.!~*'()")
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(component.encode("utf-8")) + compressor.flush()
    payload = {"type": "xml", "compressed": True, "data": base64.b64encode(compressed).decode("ascii")}
    url = "https://app.diagrams.net/?lightbox=1&edit=_blank&border=10#create=" + urllib.parse.quote(
        json.dumps(payload, separators=(",", ":")), safe=""
    )
    restored_payload = json.loads(urllib.parse.unquote(url.split("#create=", 1)[1]))
    restored_component = zlib.decompress(
        base64.b64decode(restored_payload["data"], validate=True), wbits=-15
    ).decode("utf-8")
    restored = urllib.parse.unquote(restored_component).encode("utf-8")
    if restored != xml:
        raise RuntimeError("official #create payload roundtrip mismatch")
    ET.fromstring(restored)
    return url


def path_safe(path: Path) -> bool:
    if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".log", ".tmp"}:
        return False
    rel = str(path.relative_to(ROOT))
    if rel in VOLATILE or rel == "validation/manifest.json":
        return False
    return path.name not in {"PACKAGE-MANIFEST.json", "SHA256SUMS.txt"}


def main() -> int:
    generated, gallery, validation = ROOT / "generated", ROOT / "gallery", ROOT / "validation"
    clear(generated)
    clear(gallery)
    validation.mkdir(exist_ok=True)
    for name in ("proof-report.json", "source-boundary-scan.txt", "manifest.json"):
        target = validation / name
        if target.exists():
            target.unlink()

    rows: list[dict[str, object]] = []
    cards: list[str] = []
    precision_totals = {"explicit": 0, "inferred": 0, "rendered": 0, "unresolved": 0}

    for name, events in fixtures().items():
        out = generated / name
        out.mkdir(parents=True)
        event_text = "".join(
            json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for event in events
        )
        model = build_model(events)
        svg = render_svg(model)
        image = render_image_drawio(model)
        dot = render_dot(model)
        d2 = render_d2(model)
        summary = render_text(model)
        metrics = measure_model(model)
        for key, value in metrics["edgePathPrecisionCounts"].items():
            precision_totals[key] += value

        hashes = {
            "events": write(out / "events.jsonl", event_text),
            "model": write(out / "model.drawio", model),
            "svg": write(out / "diagram.svg", svg),
            "imageExact": write(out / "diagram.image-exact.drawio", image),
            "dot": write(out / "graph.dot", dot),
            "d2": write(out / "graph.d2", d2),
            "text": write(out / "summary.txt", summary),
            "metrics": write(out / "metrics.json", json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n"),
            "viewerUrl": write(out / "viewer.url.txt", viewer_url(model.encode("utf-8")) + "\n"),
        }
        ET.fromstring(model)
        ET.fromstring(svg)
        ET.fromstring(image)
        graphviz = False
        if shutil.which("dot"):
            subprocess.run(["dot", "-Tsvg", str(out / "graph.dot"), "-o", str(out / "graphviz.svg")], check=True)
            ET.parse(out / "graphviz.svg")
            hashes["graphviz"] = sha256((out / "graphviz.svg").read_bytes())
            graphviz = True

        root = ET.fromstring(model)
        cells = root.findall("./diagram/mxGraphModel/root//mxCell")
        row = {
            "sample": name,
            "kind": events[0]["kind"],
            "nodes": sum(cell.get("jsonlType") == "node" for cell in cells),
            "edges": sum(cell.get("jsonlType") == "edge" for cell in cells),
            "userObjects": len(root.findall("./diagram/mxGraphModel/root/object")),
            "semanticHash": semantic_hash(model),
            "visualHash": visual_hash(model),
            "metricsStatus": metrics["status"],
            "edgePathPrecisionCounts": metrics["edgePathPrecisionCounts"],
            "graphviz": graphviz,
            "hashes": hashes,
        }
        rows.append(row)
        cards.append(f"<section><h2>{name} — {events[0]['kind']}</h2><div>{svg}</div><pre>{summary}</pre></section>")

    source_files = sorted((ROOT / "src").rglob("*.py"))
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
    forbidden_hits = sorted(set(FORBIDDEN.findall(source_text)))
    independent_hits = sorted(
        str(path.relative_to(ROOT)) for path in generated.rglob("*") if path.is_file() and path.name in INDEPENDENT_ARTIFACTS
    )
    scan = {
        "sourceFiles": len(source_files),
        "forbiddenHits": forbidden_hits,
        "independentStateArtifacts": independent_hits,
    }
    write(validation / "source-boundary-scan.txt", json.dumps(scan, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    status = "PASS" if (
        len(rows) == 13
        and all(row["userObjects"] for row in rows)
        and all(row["metricsStatus"] != "error" for row in rows)
        and not forbidden_hits
        and not independent_hits
        and precision_totals["unresolved"] == 0
    ) else "FAIL"
    report = {
        "schema": "MxGraphDirectCurrentStateProof.v2",
        "status": status,
        "authority": "events.jsonl",
        "generatedIsAuthority": False,
        "sampleCount": len(rows),
        "samples": rows,
        "edgePathPrecisionCounts": precision_totals,
        "duplicateStateArtifacts": independent_hits,
        "sourceForbiddenHits": forbidden_hits,
        "publicCurrentState": "mxGraphModel",
        "claimCeiling": {
            "proven": [
                "global semantic IDs reject ambiguous edge endpoints",
                "terminal-center edge paths are inferred advisories, never model-exact",
                "semantic metadata survives in XML user objects",
                "all projections consume mxGraphModel",
                "official #create payload roundtrips byte-exactly",
                "required evidence is manifest-verified before success",
            ],
            "notProven": [
                "architecture decision acceptance and independent reviewer binding",
                "pinned diagrams.net editor open-edit-save persistence",
                "canonical DVM deletion and proof-runtime retirement",
            ],
        },
    }
    write(validation / "proof-report.json", json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    html = "<!doctype html><html><head><meta charset='utf-8'><title>mxGraph proof</title></head><body><h1>events.jsonl → mxGraphModel → projections</h1>" + "".join(cards) + "</body></html>"
    write(gallery / "index.html", html)

    manifest_files = []
    for path in sorted(ROOT.rglob("*")):
        if path_safe(path):
            manifest_files.append({
                "path": str(path.relative_to(ROOT)),
                "size": path.stat().st_size,
                "sha256": sha256(path.read_bytes()),
            })
    write(validation / "manifest.json", json.dumps({"schema": "ProofManifest.v1", "files": manifest_files}, indent=2, sort_keys=True) + "\n")

    errors = verify_required_evidence(ROOT)
    if errors:
        raise RuntimeError("required proof evidence invalid: " + "; ".join(errors))
    print(json.dumps({"status": status, "sampleCount": len(rows), "requiredEvidence": "PASS"}, ensure_ascii=False))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
