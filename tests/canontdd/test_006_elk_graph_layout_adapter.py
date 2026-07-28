from __future__ import annotations

import unittest

from jsonl_diagram_core.elk_contract import model_to_elk_graph
from jsonl_diagram_core.mxgraph_model import build_model


class ElkGraphLayoutAdapterTest(unittest.TestCase):
    def test_elk_contract_is_derived_from_model_without_fixed_coordinates(self):
        model = build_model([
            {"op": "diagram.init", "id": "d", "kind": "architecture", "label": "D"},
            {"op": "node.upsert", "id": "a", "kind": "component", "label": "A"},
            {"op": "node.upsert", "id": "b", "kind": "component", "label": "B"},
            {"op": "edge.upsert", "id": "e", "source": "a", "target": "b", "label": "go"},
        ])
        elk = model_to_elk_graph(model)
        self.assertEqual(elk["layoutOptions"]["elk.algorithm"], "layered")
        self.assertNotIn("x", elk["children"][0])
        self.assertEqual(elk["edges"][0]["sources"], ["a"])
