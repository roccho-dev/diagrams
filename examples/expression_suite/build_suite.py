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

from jsonl_diagram_core.io import canonical_json, read_jsonl, write_jsonl, sha256_text
from jsonl_diagram_core.tokenizer import tokenize_events
from jsonl_diagram_core.reducer import reduce_tokens
from jsonl_diagram_core.proof import build_proof
from examples.adapters.d2_adapter import compile_d2, semantic_counts
from examples.adapters.graphviz_layout import layout_graphviz
from examples.adapters.svg_renderer import render_svg
from examples.adapters.drawio_renderer import render_drawio_native, render_drawio_image_exact
from jsonl_diagram_core.quality import validate_drawio_quality, validate_svg_quality


def _run_version(cmd: list[str]) -> str | None:
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=20)
    except Exception:
        return None
    out = (proc.stdout or proc.stderr or "").strip().splitlines()
    return out[0] if out else None


def engine_versions() -> dict:
    pkg = ROOT / "node_modules"
    d2_pkg = pkg / "@terrastruct" / "d2" / "package.json"
    elk_pkg = pkg / "elkjs" / "package.json"
    def npm_pkg_version(path: Path) -> str | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8")).get("version")
    return {
        "python": sys.version.split()[0],
        "node": _run_version(["node", "--version"]),
        "graphvizDot": _run_version(["dot", "-V"]),
        "terrastructD2Npm": npm_pkg_version(d2_pkg),
        "elkjsNpm": npm_pkg_version(elk_pkg),
    }


def deterministic_layout(dvm: dict) -> dict:
    nodes = dvm.get("nodes", [])
    positions = {}
    for i, n in enumerate(nodes):
        positions[n["id"]] = {"x": 64 + (i % 4) * 186, "y": 96 + (i // 4) * 104, "w": 138, "h": 56}
    return {"engine": "deterministic", "available": True, "layoutOnly": True, "fallbackUsed": True, "nodes": positions}


def maybe_elk_layout(dvm_path: Path, out_path: Path, *, require_engines: bool) -> dict:
    node = shutil.which("node")
    script = ROOT / "examples" / "adapters" / "elk_layout.mjs"
    if node and (ROOT / "node_modules" / "elkjs").exists():
        proc = subprocess.run([node, str(script), str(dvm_path), str(out_path)], cwd=ROOT, text=True, capture_output=True)
        if proc.returncode == 0 and out_path.exists():
            data = json.loads(out_path.read_text(encoding="utf-8"))
            data["fallbackUsed"] = False
            return data
        if require_engines:
            raise RuntimeError(f"ELK layout failed: {proc.stderr or proc.stdout}")
    if require_engines:
        raise RuntimeError("ELK layout required but node_modules/elkjs or node runtime is missing")
    return deterministic_layout(json.loads(dvm_path.read_text(encoding="utf-8")))


def build_one(sample_dir: Path, out_dir: Path, design_tokens: dict, *, require_engines: bool) -> dict:
    events_path = sample_dir / "events.jsonl"
    sample_out = out_dir / "samples" / sample_dir.name
    sample_out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(events_path, sample_out / "events.jsonl")
    events_text = events_path.read_text(encoding="utf-8")
    events = read_jsonl(events_path)
    tokens = tokenize_events(events)
    dvm = reduce_tokens(tokens)
    write_jsonl(sample_out / "tokens.jsonl", tokens)
    (sample_out / "dvm.json").write_text(json.dumps(dvm, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    d2 = compile_d2(dvm)
    d2_counts = semantic_counts(dvm, d2)
    if not (d2_counts["semanticNodeParity"] and d2_counts["semanticEdgeParity"] and d2_counts["adapterIdsUnique"]):
        raise RuntimeError(f"D2 semantic parity failed for {sample_dir.name}: {d2_counts}")
    (sample_out / "compiled.d2").write_text(d2, encoding="utf-8")
    kind = dvm["diagram"]["kind"]
    if kind in {"dense", "dense_dependency"}:
        layout = layout_graphviz(dvm)
        if require_engines and not layout.get("available"):
            raise RuntimeError("Graphviz layout required but dot is missing")
    elif kind in {"nested_ports", "architecture"}:
        layout = maybe_elk_layout(sample_out / "dvm.json", sample_out / "layout.json", require_engines=require_engines)
    else:
        layout = deterministic_layout(dvm)
    if require_engines and layout.get("fallbackUsed") and kind in {"dense", "dense_dependency", "nested_ports", "architecture"}:
        raise RuntimeError(f"layout fallback used for {sample_dir.name} under --require-engines")
    (sample_out / "layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    svg = render_svg(dvm, layout=layout, design_tokens=design_tokens, events_sha256=sha256_text(events_text))
    svg_quality = validate_svg_quality(svg, expected_nodes=len(dvm.get("nodes", [])), expected_edges=len(dvm.get("edges", [])), expected_groups=len(dvm.get("groups", [])))
    (sample_out / "diagram.svg").write_text(svg, encoding="utf-8")
    drawio = render_drawio_native(dvm, layout=layout, events_sha256=sha256_text(events_text))
    drawio_quality = validate_drawio_quality(drawio, expected_nodes=len(dvm.get("nodes", [])), expected_edges=len(dvm.get("edges", [])), mode="native")
    (sample_out / "diagram.drawio").write_text(drawio, encoding="utf-8")
    drawio_image = render_drawio_image_exact(svg, diagram_id=dvm.get("diagram", {}).get("id", sample_dir.name))
    drawio_image_quality = validate_drawio_quality(drawio_image, mode="image")
    (sample_out / "diagram.image-exact.drawio").write_text(drawio_image, encoding="utf-8")
    proof = build_proof(events_text=events_text, dvm=dvm, svg_text=svg, extra={
        "sample": sample_dir.name,
        "d2SemanticCounts": d2_counts,
        "layoutEngine": layout.get("engine"),
        "layoutOnly": bool(layout.get("layoutOnly")),
        "layoutFallbackUsed": bool(layout.get("fallbackUsed")),
        "htmlPreviewOnly": True,
        "htmlIncludedInZip": False,
        "svgQuality": svg_quality,
        "drawioQuality": drawio_quality,
        "drawioImageExactQuality": drawio_image_quality,
        "drawioSha256": sha256_text(drawio),
        "drawioImageExactSha256": sha256_text(drawio_image),
    })
    (sample_out / "proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"sample": sample_dir.name, "kind": kind, "nodes": len(dvm["nodes"]), "edges": len(dvm["edges"]), "layout": layout.get("engine"), "fallbackUsed": bool(layout.get("fallbackUsed")), "svgQuality": svg_quality, "drawioQuality": drawio_quality, "drawioImageExactQuality": drawio_image_quality, "proof": proof}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--require-engines", action="store_true", help="fail if Graphviz/ELK layout-only engines fall back")
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    samples_root = Path(__file__).resolve().parent / "samples"
    design_tokens = json.loads((ROOT / "design-tokens.v1.json").read_text(encoding="utf-8"))
    (out / "proof").mkdir(parents=True, exist_ok=True)
    versions = engine_versions()
    report = [build_one(s, out, design_tokens, require_engines=args.require_engines) for s in sorted(samples_root.iterdir()) if s.is_dir()]
    matrix = {
        "schema": "ExpressionCoverageMatrix.v1",
        "samples": [{"sample": r["sample"], "kind": r["kind"], "nodes": r["nodes"], "edges": r["edges"], "layout": r["layout"], "fallbackUsed": r["fallbackUsed"]} for r in report]
    }
    (out / "expression-coverage-matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema": "GeneratedManifest.v1",
        "authority": "samples/*/events.jsonl",
        "generatedIsAuthority": False,
        "htmlPreviewOnly": True,
        "htmlIncludedInZip": False,
        "drawioIncluded": True,
        "drawioModes": ["native-editable", "image-exact"],
        "requireEngines": bool(args.require_engines),
        "engineVersions": versions,
        "adapterStatus": "adapters are e2e fixtures/examples, not core library",
        "samples": matrix["samples"],
        "quality": {"svg": "validated", "drawioNative": "validated", "drawioImageExact": "validated"}
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
