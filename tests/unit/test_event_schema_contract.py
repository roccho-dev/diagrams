from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from jsonl_diagram_core.schema import EVENT_RULES, EventValidationError, validate_event
from jsonl_diagram_core.tokenizer import tokenize_events


ROOT = Path(__file__).resolve().parents[2]
PUBLIC_SCHEMA = ROOT / "schemas" / "diagram-event.v1.schema.json"
PACKAGED_SCHEMA = ROOT / "src" / "jsonl_diagram_core" / "schemas" / "diagram-event.v1.schema.json"

POSITIVE_EVENTS = [
    {"op": "diagram.init", "id": "d", "kind": "swimlane", "label": "D", "meta": {}},
    {"op": "group.upsert", "id": "g", "kind": "lane", "label": "G", "order": 1, "group": "parent", "meta": {}},
    {"op": "node.upsert", "id": "n", "kind": "task", "label": "N", "order": 1, "group": "g", "lane": "g", "meta": {}},
    {"op": "edge.upsert", "id": "e", "kind": "flow", "label": "E", "source": "n", "target": "m", "order": 1, "sourceCommandId": "cmd", "meta": {}},
    {"op": "task.upsert", "id": "t", "kind": "task", "label": "T", "lane": "g", "start": 1, "end": 2, "order": 1, "meta": {}},
    {"op": "entity.upsert", "id": "ent", "kind": "table", "label": "Ent", "order": 1, "group": "g", "meta": {"columns": ["id", ["name", "text"]]}},
    {"op": "milestone.upsert", "id": "ms", "kind": "milestone", "label": "M", "order": 1, "meta": {}},
    {"op": "style.intent", "target": "n", "intent": "primary", "meta": {}},
    {"op": "layout.intent", "target": "d", "intent": "elk", "meta": {}},
    {"op": "label.update", "target": "n", "label": "N2", "sourceCommandId": "cmd", "meta": {}},
    {"op": "edge.reconnect", "id": "e", "source": "n", "target": "m", "sourcePort": "out", "targetPort": "in", "sourceCommandId": "cmd", "meta": {}},
    {"op": "lane.assign", "id": "n", "lane": "g", "sourceCommandId": "cmd", "meta": {}},
    {"op": "span.update", "id": "n", "start": 2, "end": 3, "sourceCommandId": "cmd", "meta": {}},
    {"op": "visual.position.set", "target": "n", "x": 1.0, "y": 2, "w": 3, "h": 4.5, "lock": True, "sourceCommandId": "cmd", "meta": {}},
    {"op": "visual.edge.bendpoint.set", "id": "e", "points": [{"x": 1, "y": 2}], "sourceCommandId": "cmd", "meta": {}},
]

REJECTED_SHAPES = {
    "unknown": {"op": "node.upsert", "id": "n2", "kind": "task", "label": "N", "unexpected": True},
    "misplaced": {"op": "label.update", "id": "n", "label": "N2"},
    "contradictory": {"op": "visual.position.set", "target": "n", "x": 1, "y": 2, "lock": "yes"},
    "cross_operation": {"op": "edge.reconnect", "id": "e", "source": "n", "target": "m", "lane": "g"},
}


class EventSchemaContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.public_schema = json.loads(PUBLIC_SCHEMA.read_text(encoding="utf-8"))
        cls.packaged_schema = json.loads(PACKAGED_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.public_schema)
        cls.validator = Draft202012Validator(cls.public_schema)

    def test_schema_copies_are_equivalent(self) -> None:
        self.assertEqual(self.public_schema, self.packaged_schema)

    def test_operation_branches_match_runtime_field_contracts(self) -> None:
        branches = {}
        for definition in self.public_schema["$defs"].values():
            properties = definition.get("properties", {})
            op = properties.get("op", {}).get("const")
            if op:
                branches[op] = definition

        self.assertEqual(set(EVENT_RULES), set(branches))
        for op, rule in EVENT_RULES.items():
            branch = branches[op]
            self.assertEqual(rule["required"], set(branch["required"]), op)
            self.assertEqual(rule["allowed"], set(branch["properties"]), op)
            self.assertFalse(branch["additionalProperties"], op)

    def test_positive_shape_for_every_operation_matches_runtime_and_schema(self) -> None:
        self.assertEqual(set(EVENT_RULES), {event["op"] for event in POSITIVE_EVENTS})
        for event in POSITIVE_EVENTS:
            with self.subTest(op=event["op"]):
                self.assertEqual([], validate_event(event))
                self.validator.validate(event)

    def test_unknown_misplaced_contradictory_and_cross_operation_fields_reject_before_append(self) -> None:
        events = [
            {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
            {"op": "node.upsert", "id": "n", "kind": "component", "label": "N"},
            {"op": "node.upsert", "id": "m", "kind": "component", "label": "M"},
            {"op": "edge.upsert", "id": "e", "source": "n", "target": "m"},
        ]
        before = list(events)

        for category, candidate in REJECTED_SHAPES.items():
            with self.subTest(category=category):
                self.assertFalse(self.validator.is_valid(candidate))
                self.assertTrue(validate_event(candidate))
                with self.assertRaises(EventValidationError):
                    tokenize_events([*events, candidate])
                self.assertEqual(before, events)
                self.assertNotIn(candidate, events)


if __name__ == "__main__":
    unittest.main()
