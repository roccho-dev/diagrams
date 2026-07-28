from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from examples.adapters.d2_adapter import compile_d2, semantic_counts
from examples.adapters.drawio_renderer import render_drawio_image_exact, render_drawio_native
from examples.adapters.graphviz_layout import layout_graphviz
from examples.adapters.svg_renderer import render_svg
from jsonl_diagram_core.io import read_jsonl, sha256_text, write_jsonl
from jsonl_diagram_core.mxgraph_model import build_model
from jsonl_diagram_core.mxgraph_projection import semantic_snapshot
from jsonl_diagram_core.proof import build_proof
from jsonl_diagram_core.quality import validate_drawio_quality, validate_svg_quality
from jsonl_diagram_core.tokenizer import tokenize_events


def _run_version(command: list[str]) -> str | None:
    if not shutil.which(command[0]):
        return None
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=20)
    except Exception:
        return None
    lines = (proc.stdout or proc.stderr or "").strip().splitlines()
    return lines[0] if lines else None


def _package_version(path: Path) -> str | None:
    return json.loads(path.read_text(encoding="utf-8")).get("version") if path.exists() else None


def engine_versions() -> dict:
    return {
        "python": sys.version.split()[0],
        "node": _run_version(["node", "--version"]),
        "graphvizDot": _run_version(["dot", "-V"]),
        "terrastructD2Npm": _package_version(ROOT / "node_modules/@terrastruct/d2/package.json"),
        "elkjsNpm": _package_version(ROOT / "node_modules/elkjs/package.json"),
    }


def _elk_smoke(model_path: Path, output_path: Path, *, required: bool) -> dict:
    node = shutil.which("node")
    script = ROOT / "examples/adapters/elk_layout.mjs"
    if node and (ROOT / "node_modules/elkjs").exists():
        proc = subprocess.run([node, str(script), str(model_path), str(output_path)], cwd=ROOT, text=True, capture_output=True)
        if proc.returncode == 0 and output_path.exists():
            return json.loads(output_path.read_text(encoding="utf-8"))
        if required:
            raise RuntimeError(proc.stderr or proc.stdout or "ELK projection failed")
    if required:
        raise RuntimeError("ELK runtime is required")
    return {"engine": "elk.layered", "available": False, "layoutOnly": True, "fallbackUsed": True, "nodes": {}}


def build_one(sample_dir: Path, output_dir: Path, *, require_engines: bool) -> dict:
    events_path = sample_dir / "events.jsonl"
    sample_out = output_dir / "samples" / sample_dir.name
    sample_out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(events_path, sample_out / "events.jsonl")
    events_text = events_path.read_text(encoding="utf-8")
    events = read_jsonl(events_path)
    tokens = tokenize_events(events)
    write_jsonl(sample_out / "tokens.jsonl", tokens)

    model = build_model(events)
    model_path = sample_out / "model.drawio"
    model_path.write_text(model, encoding="utf-8")
    snapshot = semantic_snapshot(model)

    d2 = compile_d2(model)
    counts = semantic_counts(model, d2)
    if not all(counts[key] for key in ("semanticNodeParity", "semanticEdgeParity", "adapterIdsUnique")):
        raise RuntimeError(f"D2 semantic parity failed for {sample_dir.name}: {counts}")
    (sample_out / "compiled.d2").write_text(d2, encoding="utf-8")

    kind = snapshot["diagram"]["kind"]
    graphviz = layout_graphviz(model)
    if require_engines and not graphviz.get("available"):
        raise RuntimeError("Graphviz is required")
    (sample_out / "graphviz-layout.json").write_text(json.dumps(graphviz, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elk = _elk_smoke(model_path, sample_out / "elk-layout.json", required=require_engines)
    if not (sample_out / "elk-layout.json").exists():
        (sample_out / "elk-layout.json").write_text(json.dumps(elk, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    events_sha = sha256_text(events_text)
    svg = render_svg(model, events_sha256=events_sha)
    svg_quality = validate_svg_quality(svg, expected_nodes=len(snapshot["nodes"]), expected_edges=len(snapshot["edges"]), expected_groups=len(snapshot["groups"]))
    (sample_out / "diagram.svg").write_text(svg, encoding="utf-8")

    native = render_drawio_native(model, events_sha256=events_sha)
    native_quality = validate_drawio_quality(native, expected_nodes=len(snapshot["nodes"]), expected_edges=len(snapshot["edges"]), mode="native")
    (sample_out / "diagram.drawio").write_text(native, encoding="utf-8")

    image = render_drawio_image_exact(svg, diagram_id=snapshot["diagram"]["id"])
    image_quality = validate_drawio_quality(image, mode="image")
    (sample_out / "diagram.image-exact.drawio").write_text(image, encoding="utf-8")

    proof = build_proof(events_text=events_text, model_xml=model, svg_text=svg, extra={
        "sample": sample_dir.name,
        "d2SemanticCounts": counts,
        "graphviz": {"available": graphviz.get("available"), "fallbackUsed": graphviz.get("fallbackUsed")},
        "elk": {"available": elk.get("available"), "fallbackUsed": elk.get("fallbackUsed")},
        "svgQuality": svg_quality,
        "drawioQuality": native_quality,
        "drawioImageExactQuality": image_quality,
        "drawioSha256": sha256_text(native),
        "drawioImageExactSha256": sha256_text(image),
    })
    (sample_out / "proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"sample": sample_dir.name, "kind": kind, "groups": len(snapshot["groups"]), "nodes": len(snapshot["nodes"]), "edges": len(snapshot["edges"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--require-engines", action="store_true")
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    samples = Path(__file__).resolve().parent / "samples"
    reports = [build_one(path, out, require_engines=args.require_engines) for path in sorted(samples.iterdir()) if path.is_dir()]
    matrix = {"schema": "ExpressionCoverageMatrix.v2", "currentState": "mxGraphModel", "samples": reports}
    (out / "expression-coverage-matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema": "GeneratedManifest.v2", "authority": "samples/*/events.jsonl", "generatedIsAuthority": False,
        "soleGeneratedCurrentState": "mxGraphModel", "independentCurrentStateArtifacts": 0,
        "drawioIncluded": True, "drawioModes": ["native-editable", "image-exact"],
        "requireEngines": bool(args.require_engines), "engineVersions": engine_versions(),
        "samples": reports, "quality": {"svg": "validated", "drawioNative": "validated", "drawioImageExact": "validated"},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
