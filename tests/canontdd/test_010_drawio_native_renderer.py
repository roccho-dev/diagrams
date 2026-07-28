from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from jsonl_diagram_core.mxgraph_model import build_model


class DrawioNativeRendererTest(unittest.TestCase):
    def test_current_state_is_native_editable_mxgraphmodel(self):
        model = build_model([
            {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
            {"op": "node.upsert", "id": "a", "kind": "process", "label": "A"},
            {"op": "node.upsert", "id": "b", "kind": "process", "label": "B"},
            {"op": "edge.upsert", "id": "e", "source": "a", "target": "b"},
        ])
        root = ET.fromstring(model)
        self.assertEqual(root.tag, "mxfile")
        self.assertIn('jsonlType="node"', model)
        self.assertIn('edge="1"', model)
