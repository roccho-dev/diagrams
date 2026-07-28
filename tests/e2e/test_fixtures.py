from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def file_bytes_by_relative_path(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


class FixtureBuildTest(unittest.TestCase):
    def test_expression_suite_builds_from_jsonl_to_one_model(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "suite"
            command = [sys.executable, str(ROOT / "examples/expression_suite/build_suite.py"), "--out", str(out)]
            if (ROOT / "node_modules/elkjs").exists() and shutil.which("dot"):
                command.append("--require-engines")
            subprocess.run(command, cwd=ROOT, check=True)
            matrix = json.loads((out / "expression-coverage-matrix.json").read_text())
            self.assertEqual(len(matrix["samples"]), 13)
            for item in matrix["samples"]:
                sample = out / "samples" / item["sample"]
                self.assertTrue((sample / "events.jsonl").exists())
                self.assertTrue((sample / "model.drawio").exists())
                self.assertFalse((sample / "dvm.json").exists())
                self.assertTrue((sample / "compiled.d2").exists())
                self.assertTrue((sample / "diagram.svg").exists())
                proof = json.loads((sample / "proof.json").read_text())
                self.assertFalse(proof["generatedIsAuthority"])
                self.assertTrue(proof["d2SemanticCounts"]["semanticNodeParity"])
                self.assertTrue(proof["d2SemanticCounts"]["semanticEdgeParity"])

    def test_adapter_id_mapping_is_injective(self):
        from examples.adapters.d2_adapter import build_id_map, compile_d2, semantic_counts
        from jsonl_diagram_core.mxgraph_model import build_model
        mapping = build_id_map(["a-b", "a_b"])
        self.assertEqual(len(set(mapping.values())), 2)
        model = build_model([
            {"op": "diagram.init", "id": "d", "kind": "flow", "label": "D"},
            {"op": "node.upsert", "id": "a-b", "kind": "process", "label": "A"},
            {"op": "node.upsert", "id": "a_b", "kind": "process", "label": "B"},
            {"op": "edge.upsert", "id": "e", "source": "a-b", "target": "a_b"},
        ])
        counts = semantic_counts(model, compile_d2(model))
        self.assertTrue(counts["adapterIdsUnique"])
        self.assertTrue(counts["semanticNodeParity"])

    def test_semantic_roundtrip_poc_builds_deterministically(self):
        with tempfile.TemporaryDirectory() as td:
            out_a = Path(td) / "a"
            out_b = Path(td) / "b"
            command = [sys.executable, str(ROOT / "tools/build_semantic_roundtrip_poc.py"), "--out"]
            subprocess.run([*command, str(out_a)], cwd=ROOT, check=True)
            subprocess.run([*command, str(out_b)], cwd=ROOT, check=True)
            report = json.loads((out_a / "semantic-roundtrip-report.json").read_text())
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(file_bytes_by_relative_path(out_a), file_bytes_by_relative_path(out_b))


if __name__ == "__main__":
    unittest.main()
