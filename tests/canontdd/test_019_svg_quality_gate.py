from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from examples.expression_suite.build_suite import main as build_expression_suite
from jsonl_diagram_core.mxgraph_projection import semantic_counts
from jsonl_diagram_core.quality import validate_svg_quality


class SvgQualityGateTest(unittest.TestCase):
    def test_expression_suite_svgs_are_model_derived_and_provenanced(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "generated"
            self.assertEqual(build_expression_suite(["--out", str(out), "--require-engines"]), 0)
            samples = sorted((out / "samples").iterdir())
            self.assertEqual(len(samples), 13)
            for sample in samples:
                counts = semantic_counts((sample / "model.drawio").read_text(encoding="utf-8"))
                result = validate_svg_quality((sample / "diagram.svg").read_text(encoding="utf-8"), expected_nodes=counts["nodes"], expected_edges=counts["edges"], expected_groups=counts["groups"])
                self.assertEqual(result["nodeCount"], counts["nodes"], sample.name)
                self.assertEqual(result["edgeCount"], counts["edges"], sample.name)
