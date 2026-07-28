from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from jsonl_diagram_core.mxgraph_model import build_model


class OfficialUserObjectEncodingTest(unittest.TestCase):
    def test_generated_user_objects_own_cell_identity(self) -> None:
        events = [json.loads(line) for line in Path("tests/fixtures/semantic_conformance/observed.events.jsonl").read_text().splitlines() if line]
        root = ET.fromstring(build_model(events))
        wrappers = [item for item in root.findall("./diagram/mxGraphModel/root/*") if item.tag in {"object", "UserObject"}]
        self.assertTrue(wrappers)
        for wrapper in wrappers:
            self.assertTrue(wrapper.get("id"))
            cell = wrapper.find("mxCell")
            self.assertIsNotNone(cell)
            self.assertIsNone(cell.get("id"))

    def test_accepted_fixture_matches_v101_encoding(self) -> None:
        root = ET.parse("tests/fixtures/semantic_conformance/expected.drawio").getroot()
        wrappers = [item for item in root.findall("./diagram/mxGraphModel/root/*") if item.tag in {"object", "UserObject"}]
        self.assertEqual(len(wrappers), 5)
        self.assertTrue(all(wrapper.get("id") and wrapper.find("mxCell").get("id") is None for wrapper in wrappers))


if __name__ == "__main__":
    unittest.main()
