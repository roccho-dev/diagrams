from __future__ import annotations

import importlib.util
import tempfile
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "build_work_view.py"
SPEC = importlib.util.spec_from_file_location("build_work_view", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ROOT / "tests" / "fixtures" / "work_view" / "minimal.drawio"
        self.source = self.fixture.read_bytes()

    def test_builds_direct_outer_mxfile_url(self) -> None:
        url, receipt = MODULE.build_work_view(self.source)
        self.assertIn("#R%3Cmxfile", url)
        restored = urllib.parse.unquote_to_bytes(url.split("#R", 1)[1])
        self.assertEqual(self.source, restored)
        self.assertEqual("viewer-r-outer-mxfile-v1", receipt["urlFormat"])
        self.assertEqual(1, receipt["pageCount"])
        self.assertEqual(2, receipt["vertexCount"])
        self.assertEqual(1, receipt["edgeCount"])
        self.assertFalse(receipt["generatedIsAuthority"])

    def test_rejects_invalid_xml(self) -> None:
        with self.assertRaisesRegex(MODULE.WorkViewError, "invalid XML"):
            MODULE.build_work_view(b"<mxfile>")

    def test_rejects_wrong_root(self) -> None:
        with self.assertRaisesRegex(MODULE.WorkViewError, "expected mxfile"):
            MODULE.build_work_view(b"<svg/>")

    def test_cli_writes_url_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            url_path = Path(tmp) / "work.url.txt"
            receipt_path = Path(tmp) / "receipt.json"
            url, receipt = MODULE.build_work_view(self.source)
            url_path.write_text(url + "\n", encoding="utf-8")
            receipt_path.write_text("{}\n", encoding="utf-8")
            self.assertTrue(url_path.read_text(encoding="utf-8").startswith(MODULE.VIEWER_BASE))
            self.assertEqual("LOCAL_CODEC_PASS", receipt["status"])


if __name__ == "__main__":
    unittest.main()
