from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from mxgraph_core import (
    ContractError,
    build_model,
    measure_model,
    parse_model,
    semantic_hash,
    validate_events,
    visual_hash,
)
from mxgraph_core.fixtures import fixtures
from build_proof import viewer_url
from verify_required_evidence import verify_required_evidence


def minimal_events() -> list[dict[str, object]]:
    return [
        {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
        {"op": "node.upsert", "id": "a", "kind": "node", "label": "A", "order": 1},
        {"op": "node.upsert", "id": "b", "kind": "node", "label": "B", "order": 2},
        {"op": "edge.upsert", "id": "e", "source": "a", "target": "b"},
    ]


class ContractCorrectionsTests(unittest.TestCase):
    def assert_rejected(self, events: list[dict[str, object]], text: str) -> None:
        with self.assertRaisesRegex(ContractError, text):
            validate_events(events)

    def test_cross_namespace_ids_are_globally_unique(self) -> None:
        cases = [
            [
                {"op": "diagram.init", "id": "same", "kind": "flow", "label": "D"},
                {"op": "group.upsert", "id": "same", "kind": "group", "label": "G"},
            ],
            [
                {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
                {"op": "group.upsert", "id": "same", "kind": "group", "label": "G"},
                {"op": "node.upsert", "id": "same", "kind": "node", "label": "N"},
            ],
            [
                {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
                {"op": "node.upsert", "id": "same", "kind": "node", "label": "N"},
                {"op": "node.upsert", "id": "b", "kind": "node", "label": "B"},
                {"op": "edge.upsert", "id": "same", "source": "same", "target": "b"},
            ],
        ]
        for events in cases:
            with self.subTest(events=events):
                self.assert_rejected(events, "globally unique")

    def test_group_parent_cycles_are_rejected(self) -> None:
        self.assert_rejected(
            [
                {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
                {"op": "group.upsert", "id": "g", "kind": "group", "label": "G", "group": "g"},
            ],
            "cycle",
        )
        self.assert_rejected(
            [
                {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
                {"op": "group.upsert", "id": "a", "kind": "group", "label": "A", "group": "b"},
                {"op": "group.upsert", "id": "b", "kind": "group", "label": "B", "group": "a"},
            ],
            "cycle",
        )

    def test_invalid_visual_geometry_is_rejected(self) -> None:
        base = minimal_events()
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                self.assert_rejected(
                    [*base, {"op": "visual.position.set", "target": "a", "x": value, "y": 0}],
                    "finite numeric",
                )
        for key, value in (("w", 0), ("w", -1), ("h", 0), ("h", -1)):
            event = {"op": "visual.position.set", "target": "a", "x": 0, "y": 0, key: value}
            self.assert_rejected([*base, event], "must be > 0")

    def test_group_and_lane_are_mutually_exclusive(self) -> None:
        self.assert_rejected(
            [
                {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
                {"op": "group.upsert", "id": "g", "kind": "group", "label": "G"},
                {"op": "group.upsert", "id": "l", "kind": "lane", "label": "L"},
                {"op": "node.upsert", "id": "n", "kind": "node", "label": "N", "group": "g", "lane": "l"},
            ],
            "both group and lane",
        )

    def test_visual_position_must_target_vertex(self) -> None:
        self.assert_rejected(
            [*minimal_events(), {"op": "visual.position.set", "target": "e", "x": 1, "y": 2}],
            "visual position target",
        )

    def test_source_command_id_must_be_valid_id(self) -> None:
        self.assert_rejected(
            [*minimal_events(), {"op": "label.update", "target": "a", "label": "A2", "sourceCommandId": 7}],
            "sourceCommandId",
        )


class GeometryPrecisionTests(unittest.TestCase):
    def test_terminal_connected_paths_are_inferred_and_strict_mode_fails(self) -> None:
        model = build_model(fixtures()["01_flow"])
        advisory = measure_model(model)
        self.assertGreater(advisory["edgePathPrecisionCounts"]["inferred"], 0)
        self.assertEqual(advisory["edgePathPrecisionCounts"]["explicit"], 0)
        self.assertTrue(advisory["edgePathWarnings"])
        self.assertFalse(advisory["modelExact"])
        strict = measure_model(model, require_exact_edges=True)
        self.assertEqual(strict["status"], "error")
        self.assertTrue(strict["edgePathErrors"])

    def test_explicit_endpoints_affect_visual_hash_only(self) -> None:
        model = build_model(fixtures()["01_flow"])
        root = parse_model(model)
        edge = next(cell for cell in root.findall("./diagram/mxGraphModel/root//mxCell") if cell.get("jsonlType") == "edge")
        geometry = edge.find("mxGeometry")
        self.assertIsNotNone(geometry)
        assert geometry is not None
        ET.SubElement(geometry, "mxPoint", {"x": "10", "y": "20", "as": "sourcePoint"})
        ET.SubElement(geometry, "mxPoint", {"x": "700", "y": "400", "as": "targetPoint"})
        changed = ET.tostring(root, encoding="unicode")
        self.assertEqual(semantic_hash(model), semantic_hash(changed))
        self.assertNotEqual(visual_hash(model), visual_hash(changed))
        metrics = measure_model(changed)
        self.assertGreater(metrics["edgePathPrecisionCounts"]["explicit"], 0)


class EvidenceAndTransportTests(unittest.TestCase):
    def _write_valid_evidence(self, root: Path) -> None:
        (root / "validation").mkdir(parents=True)
        (root / "gallery").mkdir()
        (root / "README.md").write_text("proof\n", encoding="utf-8")
        (root / "validation/proof-report.json").write_text(
            json.dumps({"status": "PASS", "sampleCount": 13}), encoding="utf-8"
        )
        (root / "validation/source-boundary-scan.txt").write_text("{}\n", encoding="utf-8")
        (root / "gallery/index.html").write_text("<html></html>\n", encoding="utf-8")
        models = []
        for index in range(13):
            path = root / "generated" / f"sample-{index:02d}" / "model.drawio"
            path.parent.mkdir(parents=True)
            path.write_text("<mxfile><diagram><mxGraphModel><root/></mxGraphModel></diagram></mxfile>\n", encoding="utf-8")
            models.append(path)
        required = [
            root / "README.md",
            root / "validation/proof-report.json",
            root / "validation/source-boundary-scan.txt",
            root / "gallery/index.html",
            *models,
        ]
        entries = [
            {"path": str(path.relative_to(root)), "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in required
        ]
        (root / "validation/manifest.json").write_text(
            json.dumps({"files": entries}), encoding="utf-8"
        )

    def test_required_evidence_fails_closed_on_missing_or_tampered_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_valid_evidence(root)
            self.assertEqual(verify_required_evidence(root), [])
            (root / "README.md").write_text("tampered\n", encoding="utf-8")
            self.assertTrue(any("sha256 mismatch" in error for error in verify_required_evidence(root)))
            (root / "gallery/index.html").unlink()
            self.assertTrue(any("missing or empty" in error for error in verify_required_evidence(root)))

    def test_official_create_payload_roundtrips_model_bytes(self) -> None:
        model = build_model(fixtures()["13_venn"]).encode("utf-8")
        url = viewer_url(model)
        self.assertIn("#create=", url)
        self.assertNotIn("#R", url)


if __name__ == "__main__":
    unittest.main()
