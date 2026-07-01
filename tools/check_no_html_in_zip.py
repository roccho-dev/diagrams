from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


def main(argv=None):
    args = argv or sys.argv
    if len(args) < 2:
        print("usage: check_no_html_in_zip.py file.zip", file=sys.stderr)
        return 2
    z = Path(args[1])
    with zipfile.ZipFile(z) as fh:
        html = [n for n in fh.namelist() if n.lower().endswith((".html", ".htm"))]
    report = {"ok": not html, "zip": str(z), "htmlCount": len(html), "html": html}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not html else 1

if __name__ == "__main__":
    raise SystemExit(main())
