#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ops-root", type=Path, required=True)
    parser.add_argument("--governance-root", type=Path, required=True)
    parser.add_argument("--diagrams-root", type=Path, required=True)
    parser.add_argument("--ops-head", required=True)
    parser.add_argument("--governance-head", required=True)
    parser.add_argument("--diagrams-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    observed_heads = {
        "ops": git_head(args.ops_root),
        "governance": git_head(args.governance_root),
        "diagrams": git_head(args.diagrams_root),
    }
    expected_heads = {
        "ops": args.ops_head,
        "governance": args.governance_head,
        "diagrams": args.diagrams_head,
    }
    if observed_heads != expected_heads:
        raise AssertionError({"expectedHeads": expected_heads, "observedHeads": observed_heads})

    ops_source = args.ops_root / "tools/github-approval-evidence.py"
    governance_source = args.governance_root / "tools/approval-receipt-verifier.py"
    ops = load_module("approval_lane_ops", ops_source)
    governance = load_module("approval_lane_governance", governance_source)

    bundle, request, observed_at = ops.fixture()
    evidence = ops.normalize_github_approval_evidence(bundle, request, observed_at)
    if evidence["status"] != "COMPLETE" or evidence["findings"] != []:
        raise AssertionError(evidence)
    if evidence["adapter_manifest_digest"] != ops.adapter_manifest_digest():
        raise AssertionError("Ops evidence is not bound to its implementation manifest")
    if governance.EXPECTED_ADAPTER_MANIFEST_DIGEST != evidence["adapter_manifest_digest"]:
        raise AssertionError("Governance does not bind the exact Ops adapter manifest")

    grants, _, subject, as_of, engine = governance.fixture()
    receipt = governance.validate_approval(grants, evidence, subject, as_of, engine)
    if receipt["status"] != "VALID" or receipt["findings"] != []:
        raise AssertionError(receipt)
    if receipt["engine_manifest_digest"] != governance.engine_manifest_digest():
        raise AssertionError("receipt is not bound to the Governance engine manifest")

    sys.path.insert(0, str(args.diagrams_root / "src"))
    from jsonl_diagram_core.approval_receipt import (  # type: ignore[import-not-found]
        ACCEPTED_ENGINE_MANIFEST_DIGEST,
        approval_receipt_digest,
        validate_approval_receipt,
    )

    if ACCEPTED_ENGINE_MANIFEST_DIGEST != receipt["engine_manifest_digest"]:
        raise AssertionError("Diagrams does not bind the exact Governance engine manifest")
    receipt_digest = approval_receipt_digest(receipt)
    errors, accepted = validate_approval_receipt(
        receipt_ref=receipt["approval_id"],
        expected_digest=receipt_digest,
        receipts={receipt["approval_id"]: receipt},
        repository=subject["repository"],
        candidate_revision=subject["candidate_revision"],
        finding={"findingDigest": subject["finding_digest"]},
        policy_digest=subject["policy_digest"],
        as_of=as_of,
    )
    if errors or accepted != receipt:
        raise AssertionError(errors)

    wrong_adapter = copy.deepcopy(evidence)
    wrong_adapter["adapter_manifest_digest"] = "sha256:" + "0" * 64
    rejected_receipt = governance.validate_approval(grants, wrong_adapter, subject, as_of, engine)
    rejected_codes = {row["code"] for row in rejected_receipt["findings"]}
    if rejected_receipt["status"] != "ERROR" or "PROVIDER_EVIDENCE_MALFORMED" not in rejected_codes:
        raise AssertionError(rejected_receipt)

    wrong_engine = copy.deepcopy(receipt)
    wrong_engine["engine_manifest_digest"] = "sha256:" + "0" * 64
    wrong_engine_errors, _ = validate_approval_receipt(
        receipt_ref=wrong_engine["approval_id"],
        expected_digest=approval_receipt_digest(wrong_engine),
        receipts={wrong_engine["approval_id"]: wrong_engine},
        repository=subject["repository"],
        candidate_revision=subject["candidate_revision"],
        finding={"findingDigest": subject["finding_digest"]},
        policy_digest=subject["policy_digest"],
        as_of=as_of,
    )
    if "APPROVAL_RECEIPT_ENGINE_UNKNOWN" not in {row["code"] for row in wrong_engine_errors}:
        raise AssertionError(wrong_engine_errors)

    nested_evidence = {
        "kind": "githubApprovalEvidence.v1",
        "repository": {},
        "pull_request": {},
        "review": {},
        "actor": {},
    }
    nested_receipt = governance.validate_approval(grants, nested_evidence, subject, as_of, engine)
    if nested_receipt["status"] != "ERROR":
        raise AssertionError(nested_receipt)

    report: dict[str, Any] = {
        "kind": "approvalLaneExactSourceE2E.v1",
        "status": "PASS",
        "heads": observed_heads,
        "sources": {
            "ops": {"path": "tools/github-approval-evidence.py", "sha256": sha256(ops_source)},
            "governance": {"path": "tools/approval-receipt-verifier.py", "sha256": sha256(governance_source)},
            "diagrams": {
                "path": "src/jsonl_diagram_core/approval_receipt.py",
                "sha256": sha256(args.diagrams_root / "src/jsonl_diagram_core/approval_receipt.py"),
            },
        },
        "opsAdapterManifestDigest": evidence["adapter_manifest_digest"],
        "governanceEngineManifestDigest": receipt["engine_manifest_digest"],
        "providerEvidenceDigest": receipt["provider_evidence_digest"],
        "approvalReceiptDigest": receipt_digest,
        "receiptStatus": receipt["status"],
        "consumerErrors": [],
        "destructiveCases": [
            "unknown Ops adapter manifest rejected by Governance",
            "unknown Governance engine manifest rejected by Diagrams",
            "legacy nested evidence shape rejected by Governance",
        ],
        "claimCeiling": receipt["claim_ceiling"],
        "authority": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
