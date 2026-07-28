from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .io import canonical_json, sha256_text

JsonObj = dict[str, Any]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_proof(*, events_text: str, model_xml: str, svg_text: str | None = None, extra: JsonObj | None = None) -> JsonObj:
    proof: JsonObj = {
        "schema": "DiagramProof.v2",
        "authority": "events.jsonl",
        "generatedIsAuthority": False,
        "eventsSha256": sha256_text(events_text),
        "modelSha256": sha256_text(model_xml),
    }
    if svg_text is not None:
        proof["svgSha256"] = sha256_text(svg_text)
    if extra:
        proof.update(extra)
    proof["proofSha256"] = sha256_text(canonical_json(proof))
    return proof
