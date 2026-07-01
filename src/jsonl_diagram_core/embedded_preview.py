from __future__ import annotations
import json
from html import escape
from typing import Any

JsonObj = dict[str, Any]

def build_embedded_preview(svgs: dict[str, str], report: JsonObj | None = None, source_jsonl: str = "") -> str:
    cards = []
    for name, svg in svgs.items():
        cards.append(f'<section class="card"><h2>{escape(name)}</h2>{svg}</section>')
    report_json = escape(json.dumps(report or {}, ensure_ascii=False, sort_keys=True))
    source = escape(source_jsonl)
    return """<!doctype html><html><head><meta charset='utf-8'><title>jsonl diagram preview</title><style>body{font-family:system-ui;margin:24px;background:#f8fafc}.card{background:white;border:1px solid #cbd5e1;border-radius:14px;padding:16px;margin:16px 0}svg{max-width:100%;height:auto}</style></head><body><main>""" + "\n".join(cards) + f"<script type='application/json' id='compile-report'>{report_json}</script><script type='application/jsonl' id='source-jsonl'>{source}</script></main></body></html>"

def external_reference_violations(html: str) -> list[str]:
    lowered = html.lower()
    violations = []
    for token in ("<iframe", "src=\"http", "src='http", "href=\"http", "href='http", "src=\"file:", "href=\"file:"):
        if token in lowered:
            violations.append(token)
    return violations
