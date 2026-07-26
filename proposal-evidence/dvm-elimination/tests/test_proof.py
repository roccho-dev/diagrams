from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import mxgraph_core
from mxgraph_core import (
    ContractError, apply_command, build_model, measure_model, parse_model,
    render_d2, render_dot, render_image_drawio, render_svg, render_text,
    semantic_hash, validate_events, visual_hash,
)
from mxgraph_core.fixtures import fixtures


def typed(xml_text: str, kind: str) -> list[ET.Element]:
    root = parse_model(xml_text)
    return [cell for cell in root.findall("./diagram/mxGraphModel/root//mxCell") if cell.get("jsonlType") == kind]


def by_id(xml_text: str, kind: str, raw_id: str) -> ET.Element:
    values = [cell for cell in typed(xml_text, kind) if cell.get("jsonlId") == raw_id]
    if len(values) != 1: raise AssertionError((kind, raw_id, len(values)))
    return values[0]


class DirectModelProof(unittest.TestCase):
    def test_01_all_fixtures_validate(self):
        for name, events in fixtures().items():
            with self.subTest(name=name): validate_events(events)

    def test_02_all_15_operations_are_covered(self):
        ops = {event["op"] for events in fixtures().values() for event in events}
        extra = [
            {"op":"label.update","target":"spec","label":"Spec v2"},
            {"op":"edge.reconnect","id":"handoff","source":"spec","target":"build"},
            {"op":"lane.assign","id":"spec","lane":"engineering"},
            {"op":"span.update","id":"spec","start":1,"end":2},
            {"op":"visual.position.set","target":"spec","x":10,"y":20},
            {"op":"visual.edge.bendpoint.set","id":"handoff","points":[{"x":100,"y":100}]},
        ]
        validate_events([*fixtures()["02_swimlane"], *extra])
        ops |= {event["op"] for event in extra}
        self.assertEqual(len(ops), 15)

    def test_03_all_13_kinds_build_native_models(self):
        self.assertEqual(len(fixtures()), 13)
        for name, events in fixtures().items():
            with self.subTest(name=name):
                model = build_model(events)
                self.assertEqual(parse_model(model).tag, "mxfile")
                self.assertEqual(len(typed(model, "diagram")), 1)

    def test_04_semantics_live_on_user_objects(self):
        model = build_model(fixtures()["13_venn"])
        root = ET.fromstring(model)
        wrappers = root.findall("./diagram/mxGraphModel/root/object")
        self.assertGreaterEqual(len(wrappers), 12)
        self.assertTrue(all(wrapper.find("mxCell") is not None for wrapper in wrappers))
        self.assertTrue(all("jsonlId" in wrapper.attrib or wrapper.get("jsonlType") == "provenance" for wrapper in wrappers))

    def test_05_venn_members_survive(self):
        model = build_model(fixtures()["13_venn"])
        cell = by_id(model, "node", "core_overlap")
        self.assertEqual(json.loads(cell.get("metaJson", "{}"))["members"], ["agent", "governance", "design"])

    def test_06_erd_columns_and_kind_survive(self):
        cell = by_id(build_model(fixtures()["07_erd"]), "node", "user")
        self.assertEqual(cell.get("semanticKind"), "table")
        self.assertEqual(cell.get("opClass"), "entity")
        self.assertEqual(json.loads(cell.get("metaJson", "{}"))["columns"][0]["name"], "id")

    def test_07_generation_is_deterministic(self):
        for name, events in fixtures().items():
            with self.subTest(name=name): self.assertEqual(build_model(events), build_model(json.loads(json.dumps(events))))

    def test_08_all_projection_families_consume_the_model(self):
        for name, events in fixtures().items():
            with self.subTest(name=name):
                model = build_model(events)
                ET.fromstring(render_svg(model)); ET.fromstring(render_image_drawio(model))
                self.assertTrue(render_text(model)); self.assertTrue(render_dot(model).startswith("digraph G")); self.assertTrue(render_d2(model).startswith("direction: right"))

    def test_09_visual_edit_changes_only_visual_hash(self):
        events = fixtures()["01_flow"]
        result = apply_command(events, {"type":"MoveNodeVisual","commandId":"v1","targetId":"work","x":422,"y":330,"lock":True})
        proof = result["proof"]
        self.assertTrue(proof["accepted"]); self.assertEqual(proof["semanticHashBefore"], proof["semanticHashAfter"]); self.assertNotEqual(proof["visualHashBefore"], proof["visualHashAfter"])

    def test_10_semantic_edit_changes_only_semantic_hash(self):
        events = fixtures()["01_flow"]
        result = apply_command(events, {"type":"RenameNode","commandId":"s1","targetId":"work","value":"Work v2"})
        proof = result["proof"]
        self.assertTrue(proof["accepted"]); self.assertNotEqual(proof["semanticHashBefore"], proof["semanticHashAfter"]); self.assertEqual(proof["visualHashBefore"], proof["visualHashAfter"])

    def test_11_invalid_command_is_rejected_before_append(self):
        events = fixtures()["01_flow"]
        result = apply_command(events, {"type":"ReconnectEdge","commandId":"bad","edgeId":"missing","source":"start","target":"end"})
        self.assertFalse(result["proof"]["accepted"]); self.assertFalse(result["proof"]["appended"]); self.assertEqual(result["events"], events)

    def test_12_all_eight_command_forms_append_valid_events(self):
        cases = [
            ("01_flow", {"type":"RenameNode","commandId":"1","targetId":"work","value":"W2"}),
            ("01_flow", {"type":"RenameEdge","commandId":"2","targetId":"e1","value":"R2"}),
            ("01_flow", {"type":"ReconnectEdge","commandId":"3","edgeId":"e1","source":"start","target":"end"}),
            ("01_flow", {"type":"ConnectEdge","commandId":"4","edgeId":"e3","source":"start","target":"end","label":"skip"}),
            ("02_swimlane", {"type":"MoveToLane","commandId":"5","targetId":"spec","laneId":"engineering"}),
            ("06_gantt", {"type":"ChangeSpan","commandId":"6","targetId":"t1","start":1,"end":4}),
            ("01_flow", {"type":"MoveNodeVisual","commandId":"7","targetId":"work","x":200,"y":250}),
            ("01_flow", {"type":"SetEdgeBendpoint","commandId":"8","edgeId":"e1","points":[{"x":120,"y":140}]}),
        ]
        for fixture, command in cases:
            with self.subTest(command=command["type"]):
                result = apply_command(fixtures()[fixture], command)
                self.assertTrue(result["proof"]["accepted"]); validate_events(result["events"])

    def test_13_geometry_metrics_include_directional_overlap(self):
        metrics = measure_model(build_model(fixtures()["13_venn"]))
        pair = next(row for row in metrics["overlaps"] if {row["a"], row["b"]} == {"agent", "governance"})
        self.assertGreater(pair["aInB"], 0); self.assertGreater(pair["bInA"], 0)

    def test_14_parent_containment_is_measured(self):
        metrics = measure_model(build_model(fixtures()["02_swimlane"]))
        self.assertTrue(metrics["containment"]); self.assertTrue(all(0 <= row["ratio"] <= 1 for row in metrics["containment"]))

    def test_15_graphviz_accepts_dot_projection(self):
        if not shutil.which("dot"): self.skipTest("dot unavailable")
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory)/"g.dot", Path(directory)/"g.svg"
            source.write_text(render_dot(build_model(fixtures()["01_flow"])), encoding="utf-8")
            subprocess.run(["dot","-Tsvg",str(source),"-o",str(target)], check=True)
            self.assertTrue(ET.parse(target).getroot().tag.endswith("svg"))

    def test_16_public_surface_has_no_custom_ir_or_snapshot(self):
        self.assertFalse(any(name.endswith("IR") for name in mxgraph_core.__all__))
        self.assertFalse(any("snapshot" in name.lower() for name in mxgraph_core.__all__))

    def test_17_editor_style_cell_normalization_preserves_semantics(self):
        model = build_model(fixtures()["13_venn"]); before = semantic_hash(model)
        root = ET.fromstring(model)
        for wrapper in root.findall("./diagram/mxGraphModel/root/object"):
            cell = wrapper.find("mxCell")
            if cell is None: continue
            for key in list(cell.attrib):
                if key.startswith("semantic") or key in {"jsonlType","jsonlId","metaJson","eventSeq","sourceOp","opClass","entityKind","value"}: cell.attrib.pop(key, None)
        normalized = ET.tostring(root, encoding="unicode")
        self.assertEqual(before, semantic_hash(normalized))
        self.assertEqual(json.loads(by_id(normalized,"node","core_overlap").get("metaJson","{}"))["members"], ["agent","governance","design"])

    def test_18_unknown_misplaced_and_ambiguous_inputs_fail_closed(self):
        cases = [
            [{"op":"unknown","id":"x"}],
            [{"op":"diagram.init","id":"d","kind":"flow","label":"D","source":"x"}],
            [{"op":"diagram.init","id":"same","kind":"flow","label":"D"},{"op":"node.upsert","id":"same","kind":"node","label":"A"},{"op":"style.intent","target":"same","intent":"x"}],
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ContractError): validate_events(case)


if __name__ == "__main__": unittest.main()
