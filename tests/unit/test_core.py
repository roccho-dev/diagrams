from __future__ import annotations

import unittest
from jsonl_diagram_core.tokenizer import tokenize_events
from jsonl_diagram_core.reducer import reduce_tokens
from jsonl_diagram_core.schema import EventValidationError, DvmValidationError, packaged_schema_path


class CoreTest(unittest.TestCase):
    def test_tokenize_reduce_minimal(self):
        events = [
            {"op":"diagram.init", "id":"d", "kind":"flow", "label":"D"},
            {"op":"node.upsert", "id":"a", "kind":"start", "label":"A"},
            {"op":"node.upsert", "id":"b", "kind":"end", "label":"B"},
            {"op":"edge.upsert", "id":"a_b", "source":"a", "target":"b", "label":"go"},
        ]
        tokens = tokenize_events(events)
        dvm = reduce_tokens(tokens)
        self.assertEqual(dvm["diagram"]["id"], "d")
        self.assertEqual(len(dvm["nodes"]), 2)
        self.assertEqual(len(dvm["edges"]), 1)
        self.assertEqual(dvm["schema"], "DiagramViewModel.v1")
        self.assertIn("hash", dvm)
        self.assertEqual(dvm["policies"]["duplicateUpsert"], "last-write-wins-with-compatible-op")

    def test_schema_rejects_missing_fields(self):
        with self.assertRaises(EventValidationError):
            tokenize_events([{"op":"edge.upsert", "id":"e", "source":"a"}])

    def test_schema_rejects_extra_fields(self):
        with self.assertRaises(EventValidationError):
            tokenize_events([{"op":"diagram.init", "id":"d", "kind":"flow", "label":"D", "extra":"no"}])

    def test_schema_rejects_runtime_type_mismatches(self):
        bad = [
            {"op":"diagram.init", "id":"d", "kind":123, "label":"D"},
            {"op":"style.intent", "target":"d", "intent":123},
            {"op":"layout.intent", "target":"d", "intent":""},
            {"op":"diagram.init", "id":"d", "kind":"flow", "label":"D", "meta":"abc"},
        ]
        for event in bad:
            with self.subTest(event=event):
                with self.assertRaises(EventValidationError):
                    tokenize_events([event])

    def test_semantic_validation_rejects_dangling_edge(self):
        events = [
            {"op":"diagram.init", "id":"d", "kind":"flow", "label":"D"},
            {"op":"node.upsert", "id":"a", "kind":"start", "label":"A"},
            {"op":"edge.upsert", "id":"e", "source":"a", "target":"missing"},
        ]
        with self.assertRaises(DvmValidationError):
            reduce_tokens(tokenize_events(events))

    def test_semantic_validation_rejects_missing_lane(self):
        events = [
            {"op":"diagram.init", "id":"d", "kind":"swimlane", "label":"D"},
            {"op":"task.upsert", "id":"a", "kind":"task", "lane":"missing", "label":"A", "start": 1, "end": 2},
        ]
        with self.assertRaises(DvmValidationError):
            reduce_tokens(tokenize_events(events))


    def test_entity_kind_is_preserved_without_losing_entity_role(self):
        events = [
            {"op":"diagram.init", "id":"erd", "kind":"erd", "label":"ERD"},
            {"op":"entity.upsert", "id":"account", "kind":"table", "label":"Account", "meta":{"columns":[["id", "PK"]]}},
        ]
        dvm = reduce_tokens(tokenize_events(events))
        node = dvm["nodes"][0]
        self.assertEqual(node["kind"], "table")
        self.assertEqual(node["opClass"], "entity")
        self.assertEqual(node["entityKind"], "table")
        self.assertEqual(node["meta"]["columns"], [["id", "PK"]])

    def test_node_and_edge_ids_are_separate_namespaces(self):
        events = [
            {"op":"diagram.init", "id":"dense", "kind":"dense", "label":"Dense"},
            {"op":"node.upsert", "id":"a", "kind":"module", "label":"A"},
            {"op":"node.upsert", "id":"d2", "kind":"module", "label":"D2"},
            {"op":"edge.upsert", "id":"d2", "source":"a", "target":"d2", "kind":"dependency", "label":""},
        ]
        dvm = reduce_tokens(tokenize_events(events))
        self.assertEqual([n["id"] for n in dvm["nodes"]], ["a", "d2"])
        self.assertEqual(dvm["edges"][0]["id"], "d2")

    def test_ambiguous_intent_target_is_rejected_when_node_and_edge_share_id(self):
        events = [
            {"op":"diagram.init", "id":"dense", "kind":"dense", "label":"Dense"},
            {"op":"node.upsert", "id":"a", "kind":"module", "label":"A"},
            {"op":"node.upsert", "id":"d2", "kind":"module", "label":"D2"},
            {"op":"edge.upsert", "id":"d2", "source":"a", "target":"d2", "kind":"dependency", "label":""},
            {"op":"style.intent", "target":"d2", "intent":"highlight"},
        ]
        with self.assertRaises(DvmValidationError):
            reduce_tokens(tokenize_events(events))

    def test_schema_is_packaged(self):
        path = packaged_schema_path()
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
