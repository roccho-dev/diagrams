from __future__ import annotations
import unittest
from jsonl_diagram_core.render_ast import render_ast, validate_render_ast

class RenderAstContractTest(unittest.TestCase):
    def test_validates_and_sorts_by_z(self):
        ast = render_ast("d", [{"id":"b","type":"box","x":0,"y":0,"width":10,"height":10,"z":2},{"id":"a","type":"text","x":0,"y":0,"width":10,"height":10,"z":1}])
        self.assertEqual([i["id"] for i in ast["items"]], ["a", "b"])

    def test_rejects_unknown_shape(self):
        with self.assertRaises(ValueError):
            validate_render_ast({"items":[{"id":"x","type":"triangle"}]})
