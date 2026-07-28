from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonl_diagram_core.mxgraph_model import build_model, parse_model, semantic_hash, visual_hash
from jsonl_diagram_core.mxgraph_projection import render_d2, render_dot, render_svg, semantic_snapshot


EVENTS = [
    {"op": "diagram.init", "id": "d", "kind": "architecture", "label": "D"},
    {"op": "group.upsert", "id": "pkg", "kind": "package", "label": "Package"},
    {"op": "node.upsert", "id": "a", "kind": "component", "label": "A", "group": "pkg", "meta": {"role": "source"}},
    {"op": "node.upsert", "id": "b", "kind": "component", "label": "B"},
    {"op": "edge.upsert", "id": "e", "source": "a", "target": "b", "kind": "depends"},
]


class CanonicalCutoverContractTest(unittest.TestCase):
    def test_accepted_adrs_identity_is_exact(self):
        identity = json.loads(Path("contracts/mxgraph_current_state/v1/identity.json").read_text())
        self.assertEqual(identity["adrsMergedCommit"], "2ae2830c211057274e0900440ea7b9a1c9e0e9ad")
        self.assertTrue(identity["mxGraphModelSoleGeneratedCurrentState"])
        self.assertFalse(identity["generatedStateAuthority"])

    def test_model_is_deterministic(self):
        self.assertEqual(build_model(EVENTS), build_model(EVENTS))

    def test_model_is_native_mxfile(self):
        self.assertEqual(parse_model(build_model(EVENTS)).tag, "mxfile")

    def test_all_semantic_fields_survive(self):
        snapshot = semantic_snapshot(build_model(EVENTS))
        self.assertEqual(snapshot["nodes"][0]["meta"]["role"], "source")
        self.assertEqual(snapshot["edges"][0]["kind"], "depends")

    def test_projection_families_read_same_model(self):
        model = build_model(EVENTS)
        self.assertIn("<svg", render_svg(model))
        self.assertIn("digraph G", render_dot(model))
        self.assertIn("direction: right", render_d2(model))

    def test_visual_change_is_semantically_isolated(self):
        before = build_model(EVENTS)
        after = build_model([*EVENTS, {"op": "visual.position.set", "target": "a", "x": 300, "y": 200}])
        self.assertEqual(semantic_hash(before), semantic_hash(after))
        self.assertNotEqual(visual_hash(before), visual_hash(after))

    def test_dangling_edge_fails_closed(self):
        bad = [*EVENTS[:-1], {"op": "edge.upsert", "id": "e", "source": "a", "target": "missing"}]
        with self.assertRaises(Exception):
            build_model(bad)

    def test_cross_kind_id_reuse_fails_closed(self):
        bad = [*EVENTS, {"op": "edge.upsert", "id": "a", "source": "a", "target": "b"}]
        with self.assertRaises(Exception):
            build_model(bad)

    def test_retired_modules_are_absent(self):
        parts = ["meaning" + "_model.py", "render" + "_ast.py", "drawio_" + "render" + "_ast.py", "svg_" + "render" + "_ast.py"]
        for name in parts:
            self.assertFalse((Path("src/jsonl_diagram_core") / name).exists())

    def test_generated_state_is_not_checked_in(self):
        self.assertFalse(Path("generated/expression-suite").exists())


if __name__ == "__main__":
    unittest.main()
