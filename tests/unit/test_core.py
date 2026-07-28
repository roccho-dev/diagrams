from __future__ import annotations

import unittest

from jsonl_diagram_core.mxgraph_model import ModelValidationError, parse_model
from jsonl_diagram_core.mxgraph_projection import semantic_snapshot
from jsonl_diagram_core.reducer import reduce_tokens
from jsonl_diagram_core.schema import EventValidationError, packaged_schema_path
from jsonl_diagram_core.tokenizer import tokenize_events


class CoreTest(unittest.TestCase):
    def test_tokenize_reduce_minimal(self):
        model = reduce_tokens(tokenize_events([
            {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
            {"op": "node.upsert", "id": "a", "kind": "start", "label": "A"},
            {"op": "node.upsert", "id": "b", "kind": "end", "label": "B"},
            {"op": "edge.upsert", "id": "a_b", "source": "a", "target": "b", "label": "go"},
        ]))
        parse_model(model)
        snapshot = semantic_snapshot(model)
        self.assertEqual(snapshot["diagram"]["id"], "d")
        self.assertEqual(len(snapshot["nodes"]), 2)
        self.assertEqual(len(snapshot["edges"]), 1)

    def test_schema_rejects_missing_fields(self):
        with self.assertRaises(EventValidationError):
            tokenize_events([{"op": "edge.upsert", "id": "e", "source": "a"}])

    def test_schema_rejects_extra_fields(self):
        with self.assertRaises(EventValidationError):
            tokenize_events([{"op": "diagram.init", "id": "d", "kind": "flow", "label": "D", "extra": "no"}])

    def test_semantic_validation_rejects_dangling_edge(self):
        with self.assertRaises(Exception):
            reduce_tokens(tokenize_events([
                {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
                {"op": "node.upsert", "id": "a", "kind": "start", "label": "A"},
                {"op": "edge.upsert", "id": "e", "source": "a", "target": "missing"},
            ]))

    def test_semantic_validation_rejects_missing_lane(self):
        with self.assertRaises(Exception):
            reduce_tokens(tokenize_events([
                {"op": "diagram.init", "id": "d", "kind": "swimlane", "label": "D"},
                {"op": "task.upsert", "id": "a", "kind": "task", "lane": "missing", "label": "A", "start": 1, "end": 2},
            ]))

    def test_entity_kind_and_columns_survive_user_object_encoding(self):
        model = reduce_tokens(tokenize_events([
            {"op": "diagram.init", "id": "erd", "kind": "erd", "label": "ERD"},
            {"op": "entity.upsert", "id": "account", "kind": "table", "label": "Account", "meta": {"columns": [["id", "PK"]]}},
        ]))
        node = semantic_snapshot(model)["nodes"][0]
        self.assertEqual(node["kind"], "table")
        self.assertEqual(node["opClass"], "entity")
        self.assertEqual(node["meta"]["columns"], [["id", "PK"]])

    def test_global_semantic_id_namespace(self):
        with self.assertRaises(EventValidationError):
            tokenize_events([
                {"op": "diagram.init", "id": "dense", "kind": "dense", "label": "Dense"},
                {"op": "node.upsert", "id": "same", "kind": "module", "label": "A"},
                {"op": "edge.upsert", "id": "same", "source": "same", "target": "same"},
            ])

    def test_schema_is_packaged(self):
        path = packaged_schema_path()
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
