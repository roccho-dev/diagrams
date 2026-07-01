from __future__ import annotations
import unittest, xml.etree.ElementTree as ET
from jsonl_diagram_core.drawio_image_mode import wrap_svg_as_drawio_image

class DrawioImageModeRendererTest(unittest.TestCase):
    def test_wraps_svg_as_image_cell_for_visual_exact_mode(self):
        xml = wrap_svg_as_drawio_image('<svg xmlns="http://www.w3.org/2000/svg"></svg>', diagram_id="d")
        ET.fromstring(xml)
        self.assertIn("data:image/svg+xml;base64", xml)
        self.assertIn('id="svg-image"', xml)
