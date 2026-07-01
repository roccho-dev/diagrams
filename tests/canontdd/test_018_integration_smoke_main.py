from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from tools.integration_smoke import run_smoke
class IntegrationSmokeMainTest(unittest.TestCase):
    def test_final_pipeline_smoke_generates_all_expected_files(self):
        with tempfile.TemporaryDirectory() as td:
            result=run_smoke(td)
            self.assertTrue(result["ok"])
            for name in result["artifacts"]: self.assertTrue((Path(td)/name).exists(),name)
