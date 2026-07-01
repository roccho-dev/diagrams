from __future__ import annotations
from pathlib import Path
from typing import Iterable
GENERATED_SUFFIXES={".svg",".drawio",".html",".png",".pdf"}
def is_generated_artifact(path: str | Path) -> bool:
    p=Path(path); return p.suffix.lower() in GENERATED_SUFFIXES or "generated" in p.parts
def authority_violations(paths: Iterable[str | Path]) -> list[str]:
    return sorted(str(Path(p)) for p in paths if is_generated_artifact(p) and "records" in Path(p).parts)
