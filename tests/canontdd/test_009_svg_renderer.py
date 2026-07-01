from __future__ import annotations
import unittest, xml.etree.ElementTree as ET
from jsonl_diagram_core.render_ast import render_ast
from jsonl_diagram_core.svg_render_ast import render_svg_from_ast

class SvgRendererTest(unittest.TestCase):
    def test_svg_from_render_ast_is_parseable(self):
        ast = render_ast("d", [{"id":"a","type":"box","x":10,"y":20,"width":80,"height":40},{"id":"label","type":"text","x":20,"y":45,"width":10,"height":10,"label":"A"}])
        svg = render_svg_from_ast(ast)
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertIn('id="a"', svg)
