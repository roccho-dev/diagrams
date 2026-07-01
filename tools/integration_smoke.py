from __future__ import annotations
import json
from pathlib import Path
from jsonl_diagram_core.io import write_jsonl
from jsonl_diagram_core.one_shot import compile_one_shot
from jsonl_diagram_core.embedded_preview import build_embedded_preview, external_reference_violations
def run_smoke(out_dir: str | Path) -> dict:
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    events=[{"op":"diagram.init","id":"smoke","kind":"flow","label":"Smoke"},{"op":"node.upsert","id":"a","kind":"start","label":"A"},{"op":"node.upsert","id":"b","kind":"end","label":"B"},{"op":"edge.upsert","id":"a_b","source":"a","target":"b","label":"go"}]
    src=out/'events.jsonl'; write_jsonl(src,events); report=compile_one_shot(src,out)
    svg=(out/'diagram.compiled.svg').read_text(encoding='utf-8')
    html=build_embedded_preview({"smoke":svg},report,src.read_text(encoding='utf-8'))
    (out/'preview.embedded.html').write_text(html,encoding='utf-8')
    result={"schema":"IntegrationSmoke.v1","ok":external_reference_violations(html)==[],"artifacts":["events.jsonl","diagram.compiled.svg","diagram.compiled.drawio","compile-report.json","preview.embedded.html"],"report":report}
    (out/'integration-smoke.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return result
