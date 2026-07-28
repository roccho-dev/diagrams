from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonl_diagram_core.mxgraph_model import build_model
from jsonl_diagram_core.semantic_conformance import compare_semantics, receipt_bytes, sha256_bytes, sha256_json

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/semantic_conformance"


class SemanticConformanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.expected = (FIXTURE / "expected.drawio").read_bytes()
        self.contract = json.loads((FIXTURE / "expected-contract.json").read_text(encoding="utf-8"))
        events = [json.loads(line) for line in (FIXTURE / "observed.events.jsonl").read_text(encoding="utf-8").splitlines() if line]
        self.observed = build_model(events).encode("utf-8")
        generator = (ROOT / "src/jsonl_diagram_core/mxgraph_model.py").read_bytes()
        revision = "a293e39890aee692f70d4e8d114d4081733a937b"
        self.provenance = {
            "kind": "diagram.observedProvenance.v1",
            "implementationRevision": revision,
            "implementationSourceDigest": sha256_json({"revision": revision, "events": sha256_bytes((FIXTURE / "observed.events.jsonl").read_bytes()), "generator": sha256_bytes(generator)}),
            "generatorDigest": sha256_bytes(generator),
            "generatedArtifactSha256": sha256_bytes(self.observed),
            "generatedAt": "2026-07-28T00:00:00Z",
            "origin": "implementation-derived",
            "expectedContentSourceUsed": False,
        }

    def test_matching_independent_artifacts_pass(self) -> None:
        receipt = compare_semantics(self.expected, self.observed, self.contract, self.provenance)
        self.assertEqual("PASS", receipt["comparison"]["status"])
        self.assertTrue(receipt["comparison"]["visual_only"])
        self.assertEqual(receipt["expected"]["semantic_sha256"], receipt["observed"]["semantic_sha256"])

    def test_relation_kind_change_fails(self) -> None:
        changed = self.observed.replace(b'semanticKind="produces"', b'semanticKind="depends_on"', 1)
        provenance = dict(self.provenance, generatedArtifactSha256=sha256_bytes(changed))
        receipt = compare_semantics(self.expected, changed, self.contract, provenance)
        self.assertEqual("FAIL", receipt["comparison"]["status"])
        self.assertEqual("graph_changed", receipt["comparison"]["changed"][0]["code"])

    def test_missing_provenance_is_error(self) -> None:
        provenance = dict(self.provenance)
        provenance.pop("implementationRevision")
        receipt = compare_semantics(self.expected, self.observed, self.contract, provenance)
        self.assertEqual("ERROR", receipt["comparison"]["status"])
        self.assertEqual("MISSING_PROVENANCE", receipt["comparison"]["errors"][0]["code"])

    def test_receipt_bytes_are_deterministic(self) -> None:
        a = compare_semantics(self.expected, self.observed, self.contract, self.provenance)
        b = compare_semantics(self.expected, self.observed, self.contract, self.provenance)
        self.assertEqual(receipt_bytes(a), receipt_bytes(b))


if __name__ == "__main__":
    unittest.main()
