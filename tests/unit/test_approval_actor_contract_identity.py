from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from jsonl_diagram_core.approval_receipt import ACCEPTED_ENGINE_MANIFEST_DIGEST


class ApprovalActorContractIdentityTest(unittest.TestCase):
    def test_exact_upstream_schema_and_engine_identity(self):
        root = Path(__file__).resolve().parents[2]
        identity = json.loads((root / "contracts/approval_actor/v1/identity.json").read_text(encoding="utf-8"))
        schema_path = root / "contracts/approval_actor/v1/approval-receipt.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_digest = "sha256:" + hashlib.sha256(
            json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        self.assertEqual(identity["contractDigest"], "sha256:21abaeb0cfb4f76babe7f1f530d14e807ef1c236e891257199490a8c0bb9d03e")
        self.assertEqual(schema_digest, identity["approvalReceiptSchemaDigest"])
        self.assertEqual(identity["approvalReceiptSchemaDigest"], "sha256:d3d52f076a94dce2693827aebecae7fdc18d5345bd2e0be39c85f090bc028ff4")
        self.assertEqual(identity["governanceEngineManifestDigest"], ACCEPTED_ENGINE_MANIFEST_DIGEST)
        self.assertEqual(identity["onlyActionKind"], "pull_request_review.approve")
        self.assertNotIn("engine_digest", schema["properties"])
        self.assertEqual(schema["properties"]["action"]["properties"]["kind"]["const"], "pull_request_review.approve")


if __name__ == "__main__":
    unittest.main()
