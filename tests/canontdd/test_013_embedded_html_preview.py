from __future__ import annotations
import unittest
from jsonl_diagram_core.embedded_preview import build_embedded_preview, external_reference_violations

class EmbeddedHtmlPreviewTest(unittest.TestCase):
    def test_preview_is_self_contained_without_websandbox(self):
        html = build_embedded_preview({"a":"<svg xmlns='http://www.w3.org/2000/svg'></svg>"}, {"ok": True}, '{"op":"diagram.init"}')
        self.assertEqual(external_reference_violations(html), [])
        self.assertIn("application/jsonl", html)
        self.assertIn("compile-report", html)
