from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonl_diagram_core.quality import validate_drawio_quality, validate_svg_quality


class FinalQualityMergeTest(unittest.TestCase):
    def test_generated_expression_suite_contains_checked_svg_and_drawio_for_every_sample(self):
        root = Path('generated/expression-suite/samples')
        self.assertTrue(root.exists())
        samples = sorted(p for p in root.iterdir() if p.is_dir())
        self.assertEqual(len(samples), 13)
        for sample in samples:
            dvm = json.loads((sample / 'dvm.json').read_text(encoding='utf-8'))
            validate_svg_quality(
                (sample / 'diagram.svg').read_text(encoding='utf-8'),
                expected_nodes=len(dvm.get('nodes', [])),
                expected_edges=len(dvm.get('edges', [])),
                expected_groups=len(dvm.get('groups', [])),
            )
            validate_drawio_quality(
                (sample / 'diagram.drawio').read_text(encoding='utf-8'),
                expected_nodes=len(dvm.get('nodes', [])),
                expected_edges=len(dvm.get('edges', [])),
                mode='native',
            )
            validate_drawio_quality((sample / 'diagram.image-exact.drawio').read_text(encoding='utf-8'), mode='image')

    def test_manifest_records_drawio_quality_modes(self):
        manifest = json.loads(Path('generated/expression-suite/manifest.json').read_text(encoding='utf-8'))
        self.assertTrue(manifest['drawioIncluded'])
        self.assertEqual(manifest['drawioModes'], ['native-editable', 'image-exact'])
        self.assertEqual(manifest['quality']['svg'], 'validated')
        self.assertEqual(manifest['quality']['drawioNative'], 'validated')
        self.assertEqual(manifest['quality']['drawioImageExact'], 'validated')
