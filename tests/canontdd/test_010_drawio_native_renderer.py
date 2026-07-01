from __future__ import annotations
import unittest, xml.etree.ElementTree as ET
from jsonl_diagram_core.render_ast import render_ast
from jsonl_diagram_core.drawio_render_ast import render_drawio_from_ast

class DrawioNativeRendererTest(unittest.TestCase):
    def test_drawio_has_root_layer_and_editable_cells(self):
        ast = render_ast("d", [{"id":"a","type":"box","x":0,"y":0,"width":80,"height":40},{"id":"b","type":"ellipse","x":120,"y":0,"width":80,"height":40},{"id":"e","type":"line","source":"a","target":"b"}])
        xml = render_drawio_from_ast(ast)
        root = ET.fromstring(xml)
        self.assertEqual(root.tag, "mxfile")
        self.assertIn('id="0"', xml)
        self.assertIn('edge="1"', xml)
