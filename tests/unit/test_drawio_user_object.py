from __future__ import annotations

import unittest

from jsonl_diagram_core.decision_overlay import inspect_semantic_drawio
from jsonl_diagram_core.quality import validate_drawio_quality


class DrawioUserObjectTest(unittest.TestCase):
    def test_canonical_user_object_is_one_semantic_cell(self):
        semantic = '''<mxfile><diagram id="p1"><mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<object id="a" label="A" role="semantic-node"><mxCell vertex="1" parent="1"><mxGeometry x="20" y="20" width="80" height="40" as="geometry"/></mxCell></object>
</root></mxGraphModel></diagram></mxfile>'''
        geometry = inspect_semantic_drawio(semantic)
        self.assertTrue(geometry["semanticModelDigest"].startswith("sha256:"))
        quality = validate_drawio_quality(semantic)
        self.assertEqual(quality["vertexCount"], 1)

    def test_mismatched_wrapper_and_nested_cell_ids_fail_closed(self):
        semantic = '''<mxfile><diagram id="p1"><mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<object id="a" label="A"><mxCell id="b" vertex="1" parent="1"><mxGeometry x="20" y="20" width="80" height="40" as="geometry"/></mxCell></object>
</root></mxGraphModel></diagram></mxfile>'''
        with self.assertRaisesRegex(ValueError, "user object id mismatch"):
            inspect_semantic_drawio(semantic)
        with self.assertRaisesRegex(AssertionError, "user object id mismatch"):
            validate_drawio_quality(semantic)


if __name__ == "__main__":
    unittest.main()
