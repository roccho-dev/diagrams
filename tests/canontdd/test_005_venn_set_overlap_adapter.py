from __future__ import annotations
import unittest
from jsonl_diagram_core.venn_layout import venn_set_overlap_layout

class VennSetOverlapAdapterTest(unittest.TestCase):
    def test_three_set_overlap_is_deterministic_and_not_graph_layout(self):
        layout = venn_set_overlap_layout(
            [{"id":"design"},{"id":"engineering"},{"id":"business"}],
            [{"id":"all","sets":["design","engineering","business"],"label":"All 3"}],
        )
        self.assertEqual(layout["schema"], "VennSetOverlapLayout.v1")
        self.assertEqual(len(layout["circles"]), 3)
        self.assertEqual(layout["overlapLabels"][0]["sets"], ["design", "engineering", "business"])
