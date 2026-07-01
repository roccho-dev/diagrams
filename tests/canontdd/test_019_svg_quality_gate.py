from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from examples.expression_suite.build_suite import main as build_expression_suite
from jsonl_diagram_core.quality import validate_svg_quality


class SvgQualityGateTest(unittest.TestCase):
    def test_expression_suite_svgs_are_parseable_semantic_and_provenanced(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'generated'
            self.assertEqual(build_expression_suite(['--out', str(out), '--require-engines']), 0)
            sample_dirs = sorted((out / 'samples').iterdir())
            self.assertEqual(len(sample_dirs), 13)
            for sample in sample_dirs:
                dvm = __import__('json').loads((sample / 'dvm.json').read_text(encoding='utf-8'))
                result = validate_svg_quality(
                    (sample / 'diagram.svg').read_text(encoding='utf-8'),
                    expected_nodes=len(dvm.get('nodes', [])),
                    expected_edges=len(dvm.get('edges', [])),
                    expected_groups=len(dvm.get('groups', [])),
                )
                self.assertEqual(result['nodeCount'], len(dvm.get('nodes', [])), sample.name)
                self.assertEqual(result['edgeCount'], len(dvm.get('edges', [])), sample.name)
