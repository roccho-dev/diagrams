from __future__ import annotations
import unittest
from jsonl_diagram_core.elk_contract import dvm_to_elk_graph

class ElkGraphLayoutAdapterTest(unittest.TestCase):
    def test_elk_contract_has_no_fixed_coordinates(self):
        dvm = {"diagram":{"id":"d"},"nodes":[{"id":"a","label":"A"},{"id":"b","label":"B"}],"edges":[{"id":"e","source":"a","target":"b","label":"go"}]}
        elk = dvm_to_elk_graph(dvm)
        self.assertEqual(elk["layoutOptions"]["elk.algorithm"], "layered")
        self.assertNotIn("x", elk["children"][0])
        self.assertEqual(elk["edges"][0]["sources"], ["a"])
