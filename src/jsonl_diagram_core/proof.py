from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from .io import canonical_json, sha256_text

JsonObj = dict[str, Any]


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_proof(*, events_text: str, dvm: JsonObj, svg_text: str | None = None, extra: JsonObj | None = None) -> JsonObj:
    proof: JsonObj = {
        "schema": "DiagramProof.v1",
        "authority": "events.jsonl",
        "generatedIsAuthority": False,
        "eventsSha256": sha256_text(events_text),
        "dvmSha256": sha256_text(canonical_json(dvm)),
    }
    if svg_text is not None:
        proof["svgSha256"] = sha256_text(svg_text)
    if extra:
        proof.update(extra)
    proof["proofSha256"] = sha256_text(canonical_json(proof))
    return proof
