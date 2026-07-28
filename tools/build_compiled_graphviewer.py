#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from jsonl_diagram_core.compiled_graphviewer import build_compiled_graphviewer

p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,required=True)
p.add_argument('--viewer-runtime',type=Path,required=True)
p.add_argument('--license',type=Path,required=True)
p.add_argument('--runtime-pin',type=Path,default=Path('contracts/compiled_graphviewer/v1/runtime-pin.json'))
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
print(json.dumps(build_compiled_graphviewer(a.source,a.viewer_runtime,a.license,a.runtime_pin,a.out),indent=2,sort_keys=True))
