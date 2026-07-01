from __future__ import annotations

from pathlib import Path
from typing import Any
from .io import canonical_json, read_jsonl, sha256_text

JsonObj = dict[str, Any]

def discover_event_fixtures(root: str | Path) -> JsonObj:
    """Return stable metadata for canonical events.jsonl fixtures.

    The manifest is intentionally based on JSONL authority only; rendered SVG,
    drawio, and preview files are not treated as source material.
    """
    base = Path(root)
    sample_root = base / "examples" / "expression_suite" / "samples"
    fixtures: list[JsonObj] = []
    for path in sorted(sample_root.glob("*/events.jsonl")):
        events = read_jsonl(path)
        fixtures.append({
            "id": path.parent.name,
            "path": str(path.relative_to(base)),
            "events": len(events),
            "sha256": sha256_text(canonical_json(events)),
        })
    return {"schema": "CanonicalFixtureManifest.v1", "authority": "events.jsonl", "count": len(fixtures), "fixtures": fixtures}

def html_source_files(root: str | Path) -> list[str]:
    base = Path(root)
    ignored_parts = {".git", "generated", "validation", "proposal-evidence"}
    out: list[str] = []
    for path in base.rglob("*.html"):
        if ignored_parts.intersection(path.relative_to(base).parts):
            continue
        out.append(str(path.relative_to(base)))
    return sorted(out)
