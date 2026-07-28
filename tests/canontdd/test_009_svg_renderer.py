from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from jsonl_diagram_core.mxgraph_model import build_model
from jsonl_diagram_core.mxgraph_projection import render_svg


class SvgRendererTest(unittest.TestCase):
    def test_svg_is_projected_directly_from_mxgraphmodel(self):
        model = build_model([
            {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
            {"op": "node.upsert", "id": "a", "kind": "process", "label": "A"},
        ])
        svg = render_svg(model)
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertIn('data-jsonl-id="a"', svg)
