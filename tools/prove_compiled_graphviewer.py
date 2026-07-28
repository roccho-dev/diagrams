#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, tempfile
from pathlib import Path
from jsonl_diagram_core.compiled_graphviewer import build_compiled_graphviewer

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tests/fixtures/compiled_graphviewer/semantic-visibility.drawio'
PIN=ROOT/'contracts/compiled_graphviewer/v1/runtime-pin.json'

def expect(name, fn):
  try: fn()
  except Exception as exc: return {'case':name,'status':'PASS','rejectedBy':type(exc).__name__}
  return {'case':name,'status':'FAIL'}

def main():
  import argparse
  p=argparse.ArgumentParser(); p.add_argument('--viewer-runtime',type=Path,required=True); p.add_argument('--license',type=Path,required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
  cases=[]
  with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    def build(source=SOURCE,runtime=a.viewer_runtime,license_path=a.license,pin=PIN,name='out'):
      return build_compiled_graphviewer(source,runtime,license_path,pin,root/name)
    build(name='baseline')
    bad_runtime=root/'bad.js'; bad_runtime.write_text('bad')
    cases.append(expect('D01-runtime-digest',lambda:build(runtime=bad_runtime,name='d1')))
    bad_license=root/'bad-license'; bad_license.write_text('bad')
    cases.append(expect('D02-license-digest',lambda:build(license_path=bad_license,name='d2')))
    malformed=root/'malformed.drawio'; malformed.write_text('<mxfile>')
    cases.append(expect('D03-malformed-xml',lambda:build(source=malformed,name='d3')))
    wrong=root/'wrong.drawio'; wrong.write_text('<svg/>')
    cases.append(expect('D04-wrong-root',lambda:build(source=wrong,name='d4')))
    empty=root/'empty.drawio'; empty.write_text('<mxfile/>')
    cases.append(expect('D05-no-pages',lambda:build(source=empty,name='d5')))
    text=SOURCE.read_text()
    duplicate_page=root/'dup-page.drawio'; duplicate_page.write_text(text.replace('</mxfile>',text[text.index('<diagram'):text.rindex('</diagram>')+10]+'</mxfile>'))
    cases.append(expect('D06-duplicate-page',lambda:build(source=duplicate_page,name='d6')))
    duplicate_id=root/'dup-id.drawio'; duplicate_id.write_text(text.replace('semanticId="near"','semanticId="middle"'))
    cases.append(expect('D07-duplicate-subject',lambda:build(source=duplicate_id,name='d7')))
    nonnumeric=root/'nonnumeric.drawio'; nonnumeric.write_text(text.replace('minScreenWidthPx="90"','minScreenWidthPx="x"'))
    cases.append(expect('D08-nonnumeric-threshold',lambda:build(source=nonnumeric,name='d8')))
    negative=root/'negative.drawio'; negative.write_text(text.replace('minScreenHeightPx="36"','minScreenHeightPx="-1"'))
    cases.append(expect('D09-negative-threshold',lambda:build(source=negative,name='d9')))
    missing_id=root/'missing-id.drawio'; missing_id.write_text(text.replace('<UserObject id="middle"','<UserObject').replace('semanticId="middle" ','',1))
    cases.append(expect('D10-threshold-without-id',lambda:build(source=missing_id,name='d10')))
    external_image=root/'external-image.drawio'; external_image.write_text(text.replace('style="rounded=0;','image="https://example.com/x.png" style="rounded=0;',1))
    cases.append(expect('D11-external-image',lambda:build(source=external_image,name='d11')))
    pin=json.loads(PIN.read_text()); pin['repository']='example/drawio'; bad_repo=root/'wrong-repo.json'; bad_repo.write_text(json.dumps(pin))
    cases.append(expect('D12-wrong-runtime-repository',lambda:build(pin=bad_repo,name='d12')))
    pin=json.loads(PIN.read_text()); pin['tag']='latest'; bad_pin=root/'latest.json'; bad_pin.write_text(json.dumps(pin))
    cases.append(expect('D13-latest-runtime',lambda:build(pin=bad_pin,name='d13')))
    app=(root/'baseline/app.js').read_text()
    cases.append({'case':'D14-no-custom-renderer','status':'PASS' if not any(x in app for x in ('createElementNS(', 'getContext(', 'WebGLRenderingContext')) else 'FAIL'})
    index=(root/'baseline/index.html').read_text()
    cases.append({'case':'D15-csp-connect-none','status':'PASS' if "connect-src 'none'" in index else 'FAIL'})
    build(name='a'); build(name='b')
    digest=lambda d:{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir())}
    cases.append({'case':'D16-deterministic-bundle','status':'PASS' if digest(root/'a')==digest(root/'b') else 'FAIL'})
  result={'kind':'compiledGraphViewerDestructiveProof.v1','status':'PASS' if all(x['status']=='PASS' for x in cases) else 'FAIL','destructiveCases':cases,'caseCount':len(cases),'authority':False}
  a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n'); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
