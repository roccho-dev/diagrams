from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from jsonl_diagram_core.approval_receipt import ACCEPTED_ENGINE_MANIFEST_DIGEST


class ApprovalActorContractIdentityTest(unittest.TestCase):
    def test_exact_merged_upstream_schema_and_engine_identity(self):
        root = Path(__file__).resolve().parents[2]
        identity = json.loads((root / "contracts/approval_actor/v1/identity.json").read_text(encoding="utf-8"))
        schema_path = root / "contracts/approval_actor/v1/approval-receipt.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_digest = "sha256:" + hashlib.sha256(
            json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        self.assertEqual(identity["status"], "MERGED_UPSTREAM_IDENTITIES")
        self.assertEqual(identity["adrsAcceptedMerge"], "70244fa200d8717c61b514432c54bed4248028d9")
        self.assertEqual(identity["opsMergedCommit"], "a622192703c53fea4890a3ad3618e2a0ac85032f")
        self.assertEqual(identity["governanceMergedCommit"], "9be6d7c1413b6c9ea15c06fbed2392f7fa64219b")
        self.assertEqual(identity["admission"], "ALLOW_WITH_ACCEPTED_EXCEPTION")
        self.assertEqual(identity["admissionExceptionDigest"], "sha256:748ab4ccc62bc60c6bdc8c38a9d64d121f6fe0340907a935873c98971ca17f91")
        self.assertFalse(identity["fullCanonicalGreen"])
        self.assertEqual(identity["contractDigest"], "sha256:53e9fa1053c8a2f003765c6af2e8a90114f6470b46c9cc28d45eb3562518af0b")
        self.assertEqual(schema_digest, identity["approvalReceiptSchemaDigest"])
        self.assertEqual(identity["approvalReceiptSchemaDigest"], "sha256:d3d52f076a94dce2693827aebecae7fdc18d5345bd2e0be39c85f090bc028ff4")
        self.assertEqual(identity["opsAdapterManifestDigest"], "sha256:538ba7977bc9894bfcc2e2ae7f7e670b915f0302f318663546071d196f048724")
        self.assertEqual(identity["governanceEngineManifestDigest"], ACCEPTED_ENGINE_MANIFEST_DIGEST)
        self.assertEqual(identity["onlyActionKind"], "pull_request_review.approve")
        self.assertNotIn("engine_digest", schema["properties"])
        self.assertEqual(schema["properties"]["action"]["properties"]["kind"]["const"], "pull_request_review.approve")


if __name__ == "__main__":
    unittest.main()
