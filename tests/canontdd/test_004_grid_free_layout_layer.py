from __future__ import annotations

import unittest

from jsonl_diagram_core.grid_free_layout import grid_free_layout
from jsonl_diagram_core.mxgraph_model import build_model


class GridFreeLayoutLayerTest(unittest.TestCase):
    def test_swimlane_slots_are_derived_from_model(self):
        model = build_model([
            {"op": "diagram.init", "id": "d", "kind": "swimlane", "label": "D"},
            {"op": "group.upsert", "id": "owner", "kind": "lane", "label": "Owner", "order": 1},
            {"op": "group.upsert", "id": "ops", "kind": "lane", "label": "Ops", "order": 2},
            {"op": "node.upsert", "id": "a", "kind": "task", "label": "A", "lane": "owner", "order": 1},
            {"op": "node.upsert", "id": "b", "kind": "task", "label": "B", "lane": "owner", "order": 2},
            {"op": "node.upsert", "id": "modal", "kind": "task", "label": "M", "lane": "ops", "meta": {"overlay": True, "anchor": "a", "z": 200}},
        ])
        layout = grid_free_layout(model)
        self.assertEqual(layout["rows"], ["owner", "ops"])
        self.assertEqual([(item["id"], item["row"], item["col"]) for item in layout["placements"]], [("a", 0, 0), ("b", 0, 1), ("modal", 1, 0)])
        self.assertEqual(layout["overlays"][0]["id"], "modal")
