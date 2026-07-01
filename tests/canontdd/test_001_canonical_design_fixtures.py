from __future__ import annotations
import unittest
from pathlib import Path
from jsonl_diagram_core.canonical_fixtures import discover_event_fixtures, html_source_files

ROOT = Path(__file__).resolve().parents[2]

class CanonicalDesignFixturesTest(unittest.TestCase):
    def test_manifest_is_events_jsonl_authority_only(self):
        manifest = discover_event_fixtures(ROOT)
        self.assertEqual(manifest["authority"], "events.jsonl")
        self.assertGreaterEqual(manifest["count"], 13)
        self.assertTrue(all(f["path"].endswith("events.jsonl") for f in manifest["fixtures"]))
        self.assertTrue(all(len(f["sha256"]) == 64 for f in manifest["fixtures"]))

    def test_no_html_source_fixtures_are_promoted_to_authority(self):
        self.assertEqual(html_source_files(ROOT), [])
