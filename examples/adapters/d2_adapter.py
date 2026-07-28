from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

from jsonl_diagram_core.mxgraph_projection import render_d2, semantic_snapshot

JsonObj = dict[str, Any]
_ID_RE = re.compile(r"[^A-Za-z0-9_]")


def _stem(raw: str) -> str:
    cleaned = _ID_RE.sub("_", raw).strip("_") or "id"
    if cleaned[0].isdigit():
        cleaned = f"n_{cleaned}"
    return cleaned[:40]


def stable_adapter_id(raw: str, *, prefix: str = "n") -> str:
    value = str(raw)
    return f"{prefix}_{_stem(value)}__{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]}"


def build_id_map(raw_ids: Iterable[str], *, prefix: str = "n") -> dict[str, str]:
    mapping = {str(raw): stable_adapter_id(str(raw), prefix=prefix) for raw in raw_ids}
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("adapter id collision after stable hashing")
    return mapping


def compile_d2(model_xml: str) -> str:
    return render_d2(model_xml)


def semantic_counts(model_xml: str, d2_text: str) -> JsonObj:
    snapshot = semantic_snapshot(model_xml)
    node_decl = sum(1 for line in d2_text.splitlines() if line.strip().startswith('"') and ' -> ' not in line)
    edge_decl = sum(1 for line in d2_text.splitlines() if ' -> ' in line)
    ids = [item["id"] for item in [*snapshot["groups"], *snapshot["nodes"]]]
    return {
        "modelNodes": len(snapshot["nodes"]), "modelEdges": len(snapshot["edges"]),
        "d2NodeDecls": node_decl, "d2EdgeDecls": edge_decl,
        "adapterIdsUnique": len(set(ids)) == len(ids),
        "semanticNodeParity": node_decl == len(snapshot["groups"]) + len(snapshot["nodes"]),
        "semanticEdgeParity": edge_decl == len(snapshot["edges"]),
    }
