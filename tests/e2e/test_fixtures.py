from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FixtureBuildTest(unittest.TestCase):
    def test_expression_suite_builds_from_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "suite"
            cmd = [sys.executable, str(ROOT / "examples" / "expression_suite" / "build_suite.py"), "--out", str(out)]
            if (ROOT / "node_modules" / "elkjs").exists() and shutil.which("dot"):
                cmd.append("--require-engines")
            subprocess.run(cmd, cwd=ROOT, check=True)
            matrix = json.loads((out / "expression-coverage-matrix.json").read_text())
            self.assertGreaterEqual(len(matrix["samples"]), 12)
            for item in matrix["samples"]:
                sample = out / "samples" / item["sample"]
                self.assertTrue((sample / "events.jsonl").exists())
                self.assertTrue((sample / "dvm.json").exists())
                self.assertTrue((sample / "compiled.d2").exists())
                self.assertTrue((sample / "diagram.svg").exists())
                proof = json.loads((sample / "proof.json").read_text())
                self.assertFalse(proof["generatedIsAuthority"])
                self.assertTrue(proof["d2SemanticCounts"]["semanticNodeParity"])
                self.assertTrue(proof["d2SemanticCounts"]["semanticEdgeParity"])
                self.assertTrue(proof["d2SemanticCounts"]["adapterIdsUnique"])

    def test_adapter_id_mapping_is_injective(self):
        from jsonl_diagram_core.tokenizer import tokenize_events
        from jsonl_diagram_core.reducer import reduce_tokens
        from examples.adapters.d2_adapter import build_id_map, compile_d2, semantic_counts
        mapping = build_id_map(["a-b", "a_b"])
        self.assertEqual(len(set(mapping.values())), 2)
        dvm = reduce_tokens(tokenize_events([
            {"op":"diagram.init", "id":"d", "kind":"flow", "label":"D"},
            {"op":"node.upsert", "id":"a-b", "kind":"process", "label":"A"},
            {"op":"node.upsert", "id":"a_b", "kind":"process", "label":"B"},
            {"op":"edge.upsert", "id":"e", "source":"a-b", "target":"a_b"},
        ]))
        d2 = compile_d2(dvm)
        counts = semantic_counts(dvm, d2)
        self.assertTrue(counts["adapterIdsUnique"])
        self.assertTrue(counts["semanticNodeParity"])

    def test_semantic_roundtrip_poc_builds(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "semantic-roundtrip"
            cmd = [sys.executable, str(ROOT / "tools" / "build_semantic_roundtrip_poc.py"), "--out", str(out)]
            subprocess.run(cmd, cwd=ROOT, check=True)
            report = json.loads((out / "semantic-roundtrip-report.json").read_text())
            self.assertEqual(report["status"], "PASS")
            self.assertGreaterEqual(len(report["fixtures"]), 4)
            for item in report["fixtures"]:
                proof = out / item["proof"]
                self.assertTrue(proof.exists())


if __name__ == "__main__":
    unittest.main()
