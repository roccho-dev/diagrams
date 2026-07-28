from __future__ import annotations

import unittest

from jsonl_diagram_core.schema import EventValidationError, validate_events


class EventMeaningContractTest(unittest.TestCase):
    def test_accepts_semantic_records_without_coordinates(self):
        validate_events([
            {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
            {"op": "node.upsert", "id": "a", "kind": "service", "label": "A", "meta": {"role": "api"}},
        ])

    def test_rejects_geometry_in_semantic_upsert(self):
        with self.assertRaises(EventValidationError):
            validate_events([
                {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
                {"op": "node.upsert", "id": "a", "kind": "box", "label": "A", "x": 1},
            ])
