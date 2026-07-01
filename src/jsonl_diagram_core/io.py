from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

JsonObj = dict[str, Any]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: str | Path) -> list[JsonObj]:
    p = Path(path)
    rows: list[JsonObj] = []
    for line_no, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{p}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"{p}:{line_no}: JSONL row must be an object")
        rows.append(obj)
    return rows


def write_jsonl(path: str | Path, rows: Iterable[JsonObj]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
