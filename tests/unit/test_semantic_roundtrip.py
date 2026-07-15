from __future__ import annotations

import unittest

from jsonl_diagram_core.planes import classify_plane, projection_fingerprint
from jsonl_diagram_core.roundtrip import apply_edit_command, reject_edit_command, reduce_events

BASE_EVENTS = [
    {"op": "diagram.init", "id": "triptych", "kind": "swimlane", "label": "Triptych"},
    {"op": "group.upsert", "id": "lane.sales", "kind": "lane", "label": "Sales"},
    {"op": "group.upsert", "id": "lane.ops", "kind": "lane", "label": "Ops"},
    {"op": "task.upsert", "id": "n.qualify", "kind": "task", "lane": "lane.sales", "label": "Qualify", "start": 1, "end": 3},
    {"op": "task.upsert", "id": "n.contract", "kind": "task", "lane": "lane.ops", "label": "Contract", "start": 3, "end": 5},
    {"op": "edge.upsert", "id": "e.q_c", "source": "n.qualify", "target": "n.contract", "label": "handoff"},
]


class SemanticRoundtripTest(unittest.TestCase):
    def test_lane_progress_profiles_share_stable_ids(self):
        dvm = reduce_events(BASE_EVENTS)
        self.assertEqual(classify_plane(dvm)["plane"], "LaneProgressPlane")
        fps = [
            projection_fingerprint(dvm, profile="swimlane-lr"),
            projection_fingerprint(dvm, profile="gantt-like"),
            projection_fingerprint(dvm, profile="horizontal-sequence"),
        ]
        self.assertEqual(fps[0]["nodeIds"], fps[1]["nodeIds"])
        self.assertEqual(fps[1]["nodeIds"], fps[2]["nodeIds"])
        self.assertEqual(fps[0]["edgeIds"], fps[2]["edgeIds"])
        self.assertEqual(fps[0]["laneIds"], fps[1]["laneIds"])

    def test_rename_appends_semantic_event_and_changes_semantic_hash(self):
        result = apply_edit_command(BASE_EVENTS, {"type": "RenameNode", "commandId": "cmd.rename", "targetId": "n.qualify", "value": "Qualify enterprise lead"})
        proof = result["proof"]
        self.assertTrue(proof["accepted"])
        self.assertEqual(proof["appendedEvent"]["op"], "label.update")
        self.assertNotEqual(proof["semanticHashBefore"], proof["semanticHashAfter"])
        self.assertEqual(proof["visualHashBefore"], proof["visualHashAfter"])

    def test_visual_move_does_not_change_semantic_hash(self):
        result = apply_edit_command(BASE_EVENTS, {"type": "MoveNodeVisual", "commandId": "cmd.move", "targetId": "n.qualify", "x": 10, "y": 20, "lock": True})
        proof = result["proof"]
        self.assertEqual(proof["appendedEvent"]["op"], "visual.position.set")
        self.assertEqual(proof["semanticHashBefore"], proof["semanticHashAfter"])
        self.assertNotEqual(proof["visualHashBefore"], proof["visualHashAfter"])

    def test_invalid_reconnect_is_rejected_before_append(self):
        proof = reject_edit_command(BASE_EVENTS, {"type": "ReconnectEdge", "commandId": "cmd.bad", "edgeId": "e.q_c", "source": "n.qualify", "target": "missing"})
        self.assertFalse(proof["accepted"])
        self.assertFalse(proof["appended"])
        self.assertIn("missing", proof["error"])

    def test_graph_table_region_classification(self):
        graph = reduce_events([
            {"op": "diagram.init", "id": "g", "kind": "architecture", "label": "G"},
            {"op": "node.upsert", "id": "a", "kind": "component", "label": "A"},
            {"op": "node.upsert", "id": "b", "kind": "component", "label": "B"},
            {"op": "edge.upsert", "id": "e", "source": "a", "target": "b"},
        ])
        table = reduce_events([
            {"op": "diagram.init", "id": "t", "kind": "erd", "label": "T"},
            {"op": "entity.upsert", "id": "a", "kind": "table", "label": "A", "meta": {"columns": ["id"]}},
        ])
        region = reduce_events([
            {"op": "diagram.init", "id": "r", "kind": "venn", "label": "R"},
            {"op": "node.upsert", "id": "a", "kind": "set", "label": "A"},
        ])
        self.assertEqual(classify_plane(graph)["plane"], "GraphPlane")
        self.assertEqual(classify_plane(table)["plane"], "TablePlane")
        self.assertEqual(classify_plane(region)["plane"], "RegionPlane")


if __name__ == "__main__":
    unittest.main()
