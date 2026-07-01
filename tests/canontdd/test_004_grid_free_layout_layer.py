from __future__ import annotations
import unittest
from jsonl_diagram_core.grid_free_layout import grid_free_layout

class GridFreeLayoutLayerTest(unittest.TestCase):
    def test_swimlane_slots_are_stable_and_overlay_is_separate(self):
        dvm = {
            "groups":[{"id":"owner","kind":"lane","label":"Owner","order":1},{"id":"ops","kind":"lane","label":"Ops","order":2}],
            "nodes":[{"id":"a","lane":"owner","order":1},{"id":"b","lane":"owner","order":2},{"id":"modal","lane":"ops","order":1,"meta":{"overlay":True,"anchor":"a","z":200}}],
        }
        layout = grid_free_layout(dvm)
        self.assertEqual(layout["rows"], ["owner", "ops"])
        self.assertEqual([(p["id"], p["row"], p["col"]) for p in layout["placements"]], [("a",0,0),("b",0,1),("modal",1,0)])
        self.assertEqual(layout["overlays"][0]["id"], "modal")
