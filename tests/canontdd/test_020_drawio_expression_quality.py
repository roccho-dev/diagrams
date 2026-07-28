from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from examples.expression_suite.build_suite import main as build_expression_suite
from jsonl_diagram_core.mxgraph_projection import semantic_counts
from jsonl_diagram_core.quality import validate_drawio_quality


class DrawioExpressionQualityTest(unittest.TestCase):
    def test_native_current_state_and_image_projection_are_validated(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "generated"
            self.assertEqual(build_expression_suite(["--out", str(out), "--require-engines"]), 0)
            samples = sorted((out / "samples").iterdir())
            self.assertEqual(len(samples), 13)
            for sample in samples:
                model = (sample / "model.drawio").read_text(encoding="utf-8")
                counts = semantic_counts(model)
                native = validate_drawio_quality(model, expected_nodes=counts["nodes"], expected_edges=counts["edges"], mode="native")
                image = validate_drawio_quality((sample / "diagram.image-exact.drawio").read_text(encoding="utf-8"), mode="image")
                self.assertEqual(native["jsonlNodeCount"], counts["nodes"], sample.name)
                self.assertEqual(image["mode"], "image", sample.name)
