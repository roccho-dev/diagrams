#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET


def must_file(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"missing or empty file: {path}")
    return path


def parse_xml(path: Path, root_name: str | None = None) -> None:
    root = ET.parse(path).getroot()
    if root_name and not str(root.tag).endswith(root_name):
        raise RuntimeError(f"unexpected XML root for {path}: {root.tag}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="ci-artifacts/diagram-gallery")
    args = parser.parse_args()

    root = Path(args.root)
    out = Path(args.out)
    samples_root = root / "generated" / "expression-suite" / "samples"
    report_path = must_file(root / "validation" / "artifact-quality-report.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))

    out.mkdir(parents=True, exist_ok=True)
    artifact_dir = out / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for sample_dir in sorted(p for p in samples_root.iterdir() if p.is_dir()):
        sample = sample_dir.name
        svg = must_file(sample_dir / "diagram.svg")
        native = must_file(sample_dir / "diagram.drawio")
        image = must_file(sample_dir / "diagram.image-exact.drawio")
        parse_xml(svg, "svg")
        parse_xml(native, "mxfile")
        parse_xml(image, "mxfile")
        copied = {}
        for label, src in [("svg", svg), ("native", native), ("image", image)]:
            name = f"{sample}.{label}{src.suffix}"
            shutil.copyfile(src, artifact_dir / name)
            copied[label] = f"artifacts/{name}"
        rows.append({"sample": sample, **copied})

    expected = int(report.get("sampleCount", len(rows)))
    if len(rows) != expected:
        raise RuntimeError(f"sample count mismatch: {len(rows)} != {expected}")

    manifest = {
        "schema": "DiagramArtifactGallery.v1",
        "sampleCount": len(rows),
        "samples": rows,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(report_path, out / "artifact-quality-report.json")

    cards = []
    for row in rows:
        svg_text = (artifact_dir / Path(row["svg"]).name).read_text(encoding="utf-8")
        cards.append(
            f"<section><h2>{row['sample']}</h2>"
            f"<p><a href='{row['svg']}'>svg</a> "
            f"<a href='{row['native']}'>native drawio</a> "
            f"<a href='{row['image']}'>image-exact drawio</a></p>"
            f"<div>{svg_text}</div></section>"
        )

    html = """<!doctype html><html><head><meta charset='utf-8'><title>Diagram artifact gallery</title><style>body{font-family:sans-serif;background:#f8fafc;color:#0f172a;padding:24px}section{background:white;border:1px solid #cbd5e1;border-radius:12px;padding:16px;margin:0 0 16px}svg{max-width:100%;height:auto}</style></head><body><h1>Diagram artifact gallery</h1>""" + "".join(cards) + "</body></html>"
    (out / "index.html").write_text(html, encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
