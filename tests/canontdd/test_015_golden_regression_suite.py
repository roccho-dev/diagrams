from __future__ import annotations
import unittest
from jsonl_diagram_core.regression import compare_hash_manifest
class GoldenRegressionSuiteTest(unittest.TestCase):
    def test_reports_missing_added_and_changed_hashes(self):
        r=compare_hash_manifest({"a":"1","b":"2"},{"a":"1","b":"3","c":"4"})
        self.assertFalse(r["ok"]); self.assertEqual(r["changed"],["b"]); self.assertEqual(r["added"],["c"])
