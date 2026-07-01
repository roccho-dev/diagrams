from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

JsonObj = dict[str, Any]

_ID_RE = re.compile(r"[^A-Za-z0-9_]")


def _stem(raw: str) -> str:
    cleaned = _ID_RE.sub("_", raw).strip("_") or "id"
    if cleaned[0].isdigit():
        cleaned = f"n_{cleaned}"
    return cleaned[:40]


def stable_adapter_id(raw: str, *, prefix: str = "n") -> str:
    """Injective, renderer-safe fixture id.

    Human readability is best-effort; uniqueness comes from the raw-id hash suffix.
    """
    value = str(raw)
    return f"{prefix}_{_stem(value)}__{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]}"


def build_id_map(raw_ids: Iterable[str], *, prefix: str = "n") -> dict[str, str]:
    mapping = {str(raw): stable_adapter_id(str(raw), prefix=prefix) for raw in raw_ids}
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("adapter id collision after stable hashing")
    return mapping


def d2_id(raw: str) -> str:
    return stable_adapter_id(raw, prefix="n")


def d2_quote(text: object) -> str:
    value = str(text)
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def compile_d2(dvm: JsonObj) -> str:
    """Compile DVM to flat, semantic D2.

    Adapter fixture rule: D2 is a compile target, not authority.
    Group/nesting is preserved as metadata comments to avoid D2 nested path drift.
    Final grouped rendering is handled by the single SVG renderer fixture.
    """
    diagram = dvm["diagram"]
    nodes = dvm.get("nodes", [])
    edges = dvm.get("edges", [])
    groups = dvm.get("groups", [])
    id_map = build_id_map((n["id"] for n in nodes), prefix="n")
    lines: list[str] = [
        "# generated-from: jsonl",
        f"# diagram-id: {d2_quote(diagram.get('id', 'diagram'))}",
        f"# diagram-kind: {d2_quote(diagram.get('kind', 'diagram'))}",
        "direction: right",
        "",
    ]
    if groups:
        lines.append("# groups")
        group_map = build_id_map((g["id"] for g in groups), prefix="g")
        for g in groups:
            lines.append(f"# group {group_map[g['id']]}: label=\"{d2_quote(g.get('label', g['id']))}\" kind={d2_quote(g.get('kind','group'))}")
        lines.append("")
    lines.append("# nodes")
    for n in nodes:
        nid = id_map[n["id"]]
        shape = "rectangle"
        if n.get("kind") in {"decision", "gateway"}:
            shape = "diamond"
        elif n.get("kind") in {"start", "end"}:
            shape = "circle"
        elif n.get("kind") == "entity":
            shape = "sql_table"
        meta_group = n.get("group") or n.get("lane") or ""
        lines.append(f"{nid}: {{")
        lines.append(f"  label: \"{d2_quote(n.get('label', n['id']))}\"")
        lines.append(f"  shape: {shape}")
        lines.append(f"  # source-id: {d2_quote(n['id'])}")
        if meta_group:
            lines.append(f"  # group: {d2_quote(meta_group)}")
        lines.append("}")
    if edges:
        lines.append("")
        lines.append("# edges")
    for e in edges:
        src = id_map[e["source"]]
        tgt = id_map[e["target"]]
        label = e.get("label") or ""
        suffix = f": \"{d2_quote(label)}\"" if label else ""
        lines.append(f"{src} -> {tgt}{suffix}")
    return "\n".join(lines) + "\n"


def semantic_counts(dvm: JsonObj, d2_text: str) -> JsonObj:
    node_decl = 0
    edge_decl = 0
    seen_ids: set[str] = set()
    collision = False
    for line in d2_text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if "->" in raw:
            edge_decl += 1
        elif raw.endswith("{") and not raw.startswith("classes"):
            node_decl += 1
            adapter_id = raw[:-1].strip().rstrip(":").strip()
            collision = collision or adapter_id in seen_ids
            seen_ids.add(adapter_id)
    return {
        "dvmNodes": len(dvm.get("nodes", [])),
        "dvmEdges": len(dvm.get("edges", [])),
        "d2NodeDecls": node_decl,
        "d2EdgeDecls": edge_decl,
        "adapterIdsUnique": not collision and len(seen_ids) == node_decl,
        "semanticNodeParity": node_decl == len(dvm.get("nodes", [])),
        "semanticEdgeParity": edge_decl == len(dvm.get("edges", [])),
    }
