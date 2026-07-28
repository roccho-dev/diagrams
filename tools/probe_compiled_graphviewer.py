#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--screenshots',type=Path,required=True)
    p.add_argument('--content-mode',action='store_true')
    p.add_argument('--chromium-executable')
    a=p.parse_args()
    bundle=a.bundle.resolve(); a.out.parent.mkdir(parents=True,exist_ok=True); a.screenshots.mkdir(parents=True,exist_ok=True)
    source=(bundle/'source.drawio').read_bytes(); source_sha='sha256:'+hashlib.sha256(source).hexdigest()
    server=None
    if a.content_mode:
      base=(bundle/'index.html').as_uri(); allowed_prefix=bundle.as_uri()
    else:
      handler=lambda *args,**kwargs: Quiet(*args,directory=str(bundle),**kwargs)
      server=ThreadingHTTPServer(('127.0.0.1',0),handler)
      threading.Thread(target=server.serve_forever,daemon=True).start()
      allowed_prefix=f'http://127.0.0.1:{server.server_port}'
      base=allowed_prefix+'/index.html'
    external=[]; console_errors=[]
    with sync_playwright() as pw:
        executable=a.chromium_executable or (shutil.which('chromium') if a.content_mode else None)
        browser=pw.chromium.launch(headless=True, executable_path=executable)
        page=browser.new_page(viewport={'width':1280,'height':800},device_scale_factor=1)
        page.on('request',lambda req: external.append(req.url) if not req.url.startswith(allowed_prefix) else None)
        page.on('console',lambda msg: console_errors.append(msg.text) if msg.type=='error' else None)
        page.on('pageerror',lambda exc: console_errors.append(str(exc)))
        if a.content_mode:
          text=(bundle/'index.html').read_text(encoding='utf-8')
          match=re.search(r'<div id="viewer" class="mxgraph" data-mxgraph="([^"]*)"></div>',text)
          if not match: raise RuntimeError('viewer host not found')
          data=match.group(1)
          page.set_content('<style>html,body,#viewer{width:100%;height:100%;margin:0}#viewer{min-height:600px}</style><div id="viewer" class="mxgraph" data-mxgraph="'+data+'"></div>')
          page.add_script_tag(content=(bundle/'app.js').read_text(encoding='utf-8'))
          page.add_script_tag(content=(bundle/'viewer-static.min.js').read_text(encoding='utf-8'))
        else:
          page.goto(base,wait_until='load')
        page.wait_for_function("window.__compiledViewerProof && window.__compiledViewerProof.status === 'READY'",timeout=30000)
        snapshots={}
        for name,scale in [('far',0.3),('middle',0.7),('near',2.0)]:
          snapshots[name]=page.evaluate('(s)=>window.__setSemanticZoom(s)',scale)
          page.screenshot(path=str(a.screenshots/f'{name}.png'),full_page=True)
        proof=page.evaluate('window.__compiledViewerProof')
        rendered_svg_count=page.locator('svg').count()
        browser.close()
    if server is not None:
      server.shutdown(); server.server_close()
    visible={k:set(v['visible']) for k,v in snapshots.items()}
    assertions={
      'officialGraphViewerInitialized': proof.get('officialGraphViewerInitialized') is True,
      'sourceDigestExact': proof.get('sourceSha256')==source_sha,
      'pageCountExact': proof.get('pageCount')==1,
      'farExpected': visible['far']=={'overview'},
      'middleExpected': visible['middle']=={'overview','middle','edge-middle'},
      'nearExpected': visible['near']=={'overview','middle','near','edge-middle','edge-near'},
      'monotonicVisibility': visible['far'] <= visible['middle'] <= visible['near'],
      'hiddenEndpointEdgesAbsent': 'edge-middle' not in visible['far'] and 'edge-near' not in visible['middle'],
      'sourceModelUnchanged': (bundle/'source.drawio').read_bytes()==source,
      'consoleErrorsZero': not console_errors,
      'runtimeExternalRequestsZero': not external,
      'renderedSvgPresent': rendered_svg_count > 0,
    }
    result={
      'kind':'compiledGraphViewerBrowserProof.v1',
      'status':'PASS' if all(assertions.values()) else 'FAIL',
      'sourceSha256':source_sha,
      'assertions':assertions,
      'snapshots':snapshots,
      'consoleErrors':console_errors,
      'externalRequests':external,
      'screenshots':{p.name:'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(a.screenshots.glob('*.png'))},
      'authority':False,
    }
    a.out.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__': raise SystemExit(main())
