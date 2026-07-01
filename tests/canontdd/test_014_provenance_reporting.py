from __future__ import annotations
import unittest
from jsonl_diagram_core.provenance import provenance_report
class ProvenanceReportingTest(unittest.TestCase):
    def test_hashes_source_layout_and_artifacts(self):
        r1=provenance_report([{"op":"diagram.init"}],{"x":1},{"svg":"<svg/>"},engine="elk")
        r2=provenance_report([{"op":"diagram.init"}],{"x":1},{"svg":"<svg/>"},engine="elk")
        self.assertEqual(r1,r2); self.assertEqual(len(r1["sourceHash"]),64); self.assertEqual(r1["engine"]["name"],"elk")
