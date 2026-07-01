from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from examples.expression_suite.build_suite import main as build_expression_suite
from jsonl_diagram_core.quality import validate_drawio_quality


class DrawioExpressionQualityTest(unittest.TestCase):
    def test_expression_suite_drawio_native_and_image_exact_are_validated(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'generated'
            self.assertEqual(build_expression_suite(['--out', str(out), '--require-engines']), 0)
            sample_dirs = sorted((out / 'samples').iterdir())
            self.assertEqual(len(sample_dirs), 13)
            for sample in sample_dirs:
                dvm = json.loads((sample / 'dvm.json').read_text(encoding='utf-8'))
                native = sample / 'diagram.drawio'
                image = sample / 'diagram.image-exact.drawio'
                self.assertTrue(native.exists(), sample.name)
                self.assertTrue(image.exists(), sample.name)
                native_result = validate_drawio_quality(
                    native.read_text(encoding='utf-8'),
                    expected_nodes=len(dvm.get('nodes', [])),
                    expected_edges=len(dvm.get('edges', [])),
                    mode='native',
                )
                image_result = validate_drawio_quality(image.read_text(encoding='utf-8'), mode='image')
                self.assertEqual(native_result['jsonlNodeCount'], len(dvm.get('nodes', [])), sample.name)
                self.assertEqual(native_result['jsonlEdgeCount'], len(dvm.get('edges', [])), sample.name)
                self.assertEqual(image_result['mode'], 'image', sample.name)
