from __future__ import annotations
import unittest
from jsonl_diagram_core.authority import authority_violations, is_generated_artifact
class NoGeneratedAuthorityRuleTest(unittest.TestCase):
    def test_generated_artifacts_cannot_live_under_records_authority(self):
        self.assertTrue(is_generated_artifact("generated/a.svg"))
        self.assertEqual(authority_violations(["records/a/events.jsonl","records/a/bad.svg"]),["records/a/bad.svg"])
