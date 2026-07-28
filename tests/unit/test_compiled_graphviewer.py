from __future__ import annotations
import hashlib, os, tempfile, unittest
from pathlib import Path
from jsonl_diagram_core.compiled_graphviewer import CompiledGraphViewerError, build_compiled_graphviewer

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=Path(os.environ.get('DRAWIO_VIEWER_RUNTIME','/mnt/data/drawio-runtime/viewer-static.min.js'))
LICENSE=Path(os.environ.get('DRAWIO_VIEWER_LICENSE','/mnt/data/drawio-runtime/LICENSE'))

class CompiledGraphViewerTest(unittest.TestCase):
  def test_deterministic_bundle(self):
    if not RUNTIME.exists(): self.skipTest('local official runtime artifact unavailable')
    with tempfile.TemporaryDirectory() as tmp:
      a=Path(tmp)/'a'; b=Path(tmp)/'b'
      args=(ROOT/'tests/fixtures/compiled_graphviewer/semantic-visibility.drawio',RUNTIME,LICENSE,ROOT/'contracts/compiled_graphviewer/v1/runtime-pin.json')
      ma=build_compiled_graphviewer(*args,a); mb=build_compiled_graphviewer(*args,b)
      self.assertEqual(ma,mb)
      files=lambda root:{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
      self.assertEqual(files(a),files(b))
      self.assertEqual(0,ma['runtimeExternalRequestsAllowed'])
      self.assertFalse(ma['generatedIsAuthority'])
  def test_rejects_runtime_digest_mismatch(self):
    with tempfile.TemporaryDirectory() as tmp:
      root=Path(tmp); bad=root/'bad.js'; bad.write_text('bad')
      with self.assertRaisesRegex(CompiledGraphViewerError,'digest mismatch'):
        build_compiled_graphviewer(ROOT/'tests/fixtures/compiled_graphviewer/semantic-visibility.drawio',bad,LICENSE,ROOT/'contracts/compiled_graphviewer/v1/runtime-pin.json',root/'out')
  def test_preserves_external_links_without_fetching_them(self):
    if not RUNTIME.exists(): self.skipTest('local official runtime artifact unavailable')
    with tempfile.TemporaryDirectory() as tmp:
      manifest=build_compiled_graphviewer(ROOT/'tests/fixtures/compiled_graphviewer/semantic-visibility.drawio',RUNTIME,LICENSE,ROOT/'contracts/compiled_graphviewer/v1/runtime-pin.json',Path(tmp)/'out')
      self.assertEqual(0,manifest['runtimeExternalRequestsAllowed'])
      self.assertIn(b'data:page/id,page-two',(Path(tmp)/'out/source.drawio').read_bytes())
  def test_rejects_external_asset(self):
    if not RUNTIME.exists(): self.skipTest('local official runtime artifact unavailable')
    with tempfile.TemporaryDirectory() as tmp:
      root=Path(tmp); source=root/'external.drawio'
      source.write_text('<mxfile><diagram id="p"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="x" vertex="1" parent="1" image="https://example.com/x.png"><mxGeometry width="10" height="10" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>')
      with self.assertRaisesRegex(CompiledGraphViewerError,'external source assets'):
        build_compiled_graphviewer(source,RUNTIME,LICENSE,ROOT/'contracts/compiled_graphviewer/v1/runtime-pin.json',root/'out')

if __name__=='__main__': unittest.main()
