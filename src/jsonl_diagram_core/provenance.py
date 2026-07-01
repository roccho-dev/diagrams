from __future__ import annotations
from typing import Any
from .io import canonical_json, sha256_text
JsonObj = dict[str, Any]
def provenance_report(source: Any, layout: Any, artifacts: dict[str, str], *, engine: str, version: str = "unknown") -> JsonObj:
    return {"schema":"DiagramProvenance.v1","sourceHash":sha256_text(canonical_json(source) if not isinstance(source,str) else source),"layoutHash":sha256_text(canonical_json(layout) if not isinstance(layout,str) else layout),"artifacts":{k:sha256_text(v) for k,v in sorted(artifacts.items())},"engine":{"name":engine,"version":version}}
