from __future__ import annotations
import unittest
from jsonl_diagram_core.layout_router import choose_layout_engine

class LayoutRouterContractTest(unittest.TestCase):
    def test_routes_by_diagram_kind_without_core_engine_pollution(self):
        self.assertEqual(choose_layout_engine("dag").engine, "elk.layered")
        self.assertEqual(choose_layout_engine("swimlane").engine, "grid.free")
        self.assertEqual(choose_layout_engine("venn").engine, "venn.set-overlap")
        self.assertEqual(choose_layout_engine("sequence").engine, "plantuml.sequence")

    def test_explicit_engine_is_reported_as_explicit(self):
        decision = choose_layout_engine("flow", intent={"meta":{"engine":"graphviz.dot"}})
        self.assertEqual(decision.engine, "graphviz.dot")
        self.assertEqual(decision.reason, "explicit intent")
