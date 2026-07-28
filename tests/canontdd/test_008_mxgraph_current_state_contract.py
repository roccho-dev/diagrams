from __future__ import annotations

import unittest

from jsonl_diagram_core.mxgraph_model import build_model, parse_model
from jsonl_diagram_core.mxgraph_projection import semantic_snapshot


class MxGraphCurrentStateContractTest(unittest.TestCase):
    def test_builds_one_native_current_state_with_stable_ids(self):
        model = build_model([
            {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
            {"op": "node.upsert", "id": "a", "kind": "process", "label": "A"},
        ])
        parse_model(model)
        self.assertEqual(semantic_snapshot(model)["nodes"][0]["id"], "a")

    def test_rejects_cross_kind_semantic_id_reuse(self):
        with self.assertRaises(Exception):
            build_model([
                {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
                {"op": "node.upsert", "id": "same", "kind": "process", "label": "A"},
                {"op": "edge.upsert", "id": "same", "source": "same", "target": "same"},
            ])
