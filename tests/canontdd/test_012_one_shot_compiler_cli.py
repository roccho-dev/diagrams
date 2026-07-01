from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from jsonl_diagram_core.io import write_jsonl
from jsonl_diagram_core.one_shot import compile_one_shot
from jsonl_diagram_core.cli import main

class OneShotCompilerCliTest(unittest.TestCase):
    def test_compile_one_shot_writes_svg_drawio_and_report(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "events.jsonl"; out = Path(td) / "out"
            write_jsonl(src, [{"op":"diagram.init","id":"d","kind":"flow","label":"D"},{"op":"node.upsert","id":"a","kind":"start","label":"A"},{"op":"node.upsert","id":"b","kind":"end","label":"B"},{"op":"edge.upsert","id":"e","source":"a","target":"b"}])
            report = compile_one_shot(src, out)
            self.assertTrue((out / "diagram.compiled.svg").exists())
            self.assertTrue((out / "diagram.compiled.drawio").exists())
            self.assertEqual(len(report["sourceSha256"]), 64)
            self.assertEqual(main(["compile-bundle", str(src), "--out-dir", str(out / "cli")]), 0)
