from __future__ import annotations
import unittest
from jsonl_diagram_core.network_projection import project_network_to_dag

class NetworkProjectionAdapterTest(unittest.TestCase):
    def test_tree_like_network_can_be_projected_to_dag(self):
        p = project_network_to_dag(["core","api","db"], [("core","api"),("core","db")])
        self.assertEqual(p["root"], "core")
        self.assertTrue(p["dagProjectionSafe"])

    def test_mesh_network_reports_feedback_candidates_instead_of_hiding_them(self):
        p = project_network_to_dag(["a","b","c"], [("a","b"),("b","c"),("c","a")])
        self.assertFalse(p["dagProjectionSafe"])
        self.assertGreaterEqual(len(p["feedbackCandidates"]), 1)
