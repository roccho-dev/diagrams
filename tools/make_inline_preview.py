from __future__ import annotations

import base64
import html
import sys
from pathlib import Path


def main(argv=None):
    args = argv or sys.argv
    if len(args) < 3:
        print("usage: make_inline_preview.py generated-suite-dir out.html", file=sys.stderr)
        return 2
    root = Path(args[1])
    out = Path(args[2])
    cards = []
    for svg in sorted(root.glob("samples/*/diagram.svg")):
        b64 = base64.b64encode(svg.read_bytes()).decode("ascii")
        title = svg.parent.name
        cards.append(f'<section><h2>{html.escape(title)}</h2><img src="data:image/svg+xml;base64,{b64}" alt="{html.escape(title)}" /></section>')
    doc = f'''<!doctype html><html><head><meta charset="utf-8"><title>SVG preview only</title><style>
body{{font-family:ui-sans-serif,system-ui;margin:24px;background:#f8fafc;color:#0f172a}}section{{background:white;border:1px solid #e2e8f0;border-radius:16px;padding:16px;margin:0 0 20px;box-shadow:0 10px 30px #0f172a12}}img{{max-width:100%;height:auto;border:1px solid #e2e8f0;border-radius:12px}}.note{{color:#64748b}}
</style></head><body><h1>JSONL diagram SVG preview</h1><p class="note">Preview only. HTML is not part of the ZIP artifact. All SVGs are embedded as data URIs.</p>{''.join(cards)}</body></html>'''
    out.write_text(doc, encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
