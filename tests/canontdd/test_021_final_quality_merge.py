from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from examples.expression_suite.build_suite import main as build_expression_suite
from jsonl_diagram_core.mxgraph_projection import semantic_counts
from jsonl_diagram_core.quality import validate_drawio_quality, validate_svg_quality


class FinalQualityMergeTest(unittest.TestCase):
    def test_clean_build_contains_one_model_and_projections(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "suite"
            self.assertEqual(build_expression_suite(["--out", str(root), "--require-engines"]), 0)
            samples = sorted(path for path in (root / "samples").iterdir() if path.is_dir())
            self.assertEqual(len(samples), 13)
            for sample in samples:
                model = (sample / "model.drawio").read_text(encoding="utf-8")
                counts = semantic_counts(model)
                validate_svg_quality((sample / "diagram.svg").read_text(encoding="utf-8"), expected_nodes=counts["nodes"], expected_edges=counts["edges"], expected_groups=counts["groups"])
                validate_drawio_quality(model, expected_nodes=counts["nodes"], expected_edges=counts["edges"], mode="native")
                validate_drawio_quality((sample / "diagram.image-exact.drawio").read_text(encoding="utf-8"), mode="image")
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["soleGeneratedCurrentState"], "mxGraphModel")
            self.assertEqual(manifest["independentCurrentStateArtifacts"], 0)
