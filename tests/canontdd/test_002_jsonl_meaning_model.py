from __future__ import annotations
import unittest
from jsonl_diagram_core.meaning_model import assert_meaning_only, geometry_leaks, meaning_summary

class MeaningModelTest(unittest.TestCase):
    def test_accepts_semantic_records_without_coordinates(self):
        events = [
            {"op":"diagram.init","id":"d","kind":"flow","label":"D"},
            {"op":"node.upsert","id":"a","kind":"service","label":"A","meta":{"role":"api"}},
        ]
        assert_meaning_only(events)
        self.assertEqual(meaning_summary(events)["ops"]["node.upsert"], 1)

    def test_rejects_coordinates_in_top_level_or_meta(self):
        events = [{"op":"node.upsert","id":"a","kind":"box","label":"A","x":1,"meta":{"width":10}}]
        self.assertEqual(geometry_leaks(events), ["event[0].x", "event[0].meta.width"])
        with self.assertRaises(ValueError):
            assert_meaning_only(events)
