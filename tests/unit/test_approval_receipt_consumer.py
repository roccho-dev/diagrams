from __future__ import annotations

import copy
import unittest
from pathlib import Path

from jsonl_diagram_core import policy_gate as policy_gate_module
from jsonl_diagram_core.approval_receipt import ACCEPTED_ENGINE_MANIFEST_DIGEST, approval_receipt_digest
from jsonl_diagram_core.decision_overlay import inspect_semantic_drawio
from jsonl_diagram_core.policy_gate import gate_findings, policy_digest
from jsonl_diagram_core.receipt_overlay import project_review_drawio

REPOSITORY = "roccho-dev/diagrams"
CANDIDATE = "a" * 40
AS_OF = "2026-07-26T12:00:00+09:00"


def policy() -> dict:
    return {"schema":"DiagramPolicy.v1","maxWaiverDays":31,"rules":{
        "partial_overlap":{"effect":"INFO","waivable":False},
        "model_parent_not_containing":{"effect":"DENY","waivable":True},
        "edge_route_approximate":{"effect":"INFO","waivable":False},
        "edge_crosses_unrelated_rectangle":{"effect":"DENY","waivable":True},
    }}


def finding() -> dict:
    return {
        "ruleId":"edge_crosses_unrelated_rectangle",
        "ruleClass":"policy",
        "pageId":"p1",
        "subjectIds":["e","o"],
        "relationKind":"edge-obstacle",
        "findingKey":"F-1",
        "subjectDigest":"sha256:" + "4" * 64,
        "findingDigest":"sha256:" + "5" * 64,
        "evidence":{"edge":"e","obstacle":"o"},
    }


def receipt(current_finding: dict | None = None) -> dict:
    current_finding = current_finding or finding()
    return {
        "kind":"approvalReceipt.v1",
        "approval_id":"approval:1",
        "subject":{
            "repository":REPOSITORY,
            "candidate_revision":CANDIDATE,
            "finding_digest":current_finding["findingDigest"],
            "policy_digest":policy_digest(policy()),
        },
        "actor":{"subject_id":"role:approver","provider":"github","provider_account_id":40359643,"provider_login":"roccho-dev"},
        "action":{"kind":"pull_request_review.approve","provider_review_id":9001,"state":"APPROVED","submitted_at":"2026-07-26T10:30:00+09:00"},
        "authority":{"grant_id":"G-1","scope_digest":"sha256:"+"6"*64,"valid_from":"2026-07-01T00:00:00+09:00","valid_until":"2026-08-01T00:00:00+09:00"},
        "provider_evidence_digest":"sha256:"+"7"*64,
        "engine_manifest_digest":ACCEPTED_ENGINE_MANIFEST_DIGEST,
        "as_of":"2026-07-26T10:31:00+09:00",
        "status":"VALID",
        "findings":[],
        "claim_ceiling":{"physical_human_identity_proven":False,"account_non_compromise_proven":False,"provider_independent_non_repudiation_proven":False},
    }


def waiver(current_finding: dict | None = None, current_receipt: dict | None = None) -> dict:
    current_finding = current_finding or finding()
    current_receipt = current_receipt or receipt(current_finding)
    return {
        "schema":"DiagramWaiver.v1",
        "waiverId":"W-1",
        "findingKey":current_finding["findingKey"],
        "subjectDigest":current_finding["subjectDigest"],
        "findingDigest":current_finding["findingDigest"],
        "policyDigest":policy_digest(policy()),
        "reason":"bounded migration",
        "evidenceRefs":["adrs#257"],
        "approvalReceiptRef":current_receipt["approval_id"],
        "approvalReceiptDigest":approval_receipt_digest(current_receipt),
        "issuedAt":"2026-07-26T10:00:00+09:00",
        "expiresAt":"2026-08-01T10:00:00+09:00",
    }


def gate(*, current_finding: dict | None = None, current_waiver: dict | None = None, current_receipt: dict | None = None, current_policy: dict | None = None):
    f = current_finding or finding()
    receipts = [] if current_receipt is None else [current_receipt]
    waivers = [] if current_waiver is None else [current_waiver]
    return gate_findings(
        semantic_model_digest="sha256:"+"9"*64,
        verification="PARTIAL",
        findings=[f],
        policy=current_policy or policy(),
        waivers=waivers,
        approval_receipts=receipts,
        repository=REPOSITORY,
        candidate_revision=CANDIDATE,
        as_of=AS_OF,
    )


def accepted_case():
    f = finding(); r = receipt(f); w = waiver(f, r)
    return f, w, r


def semantic_crossing() -> str:
    return '''<mxfile><diagram id="p1" name="P1"><mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="a" value="A" vertex="1" parent="1"><mxGeometry x="20" y="80" width="80" height="40" as="geometry"/></mxCell>
<mxCell id="b" value="B" vertex="1" parent="1"><mxGeometry x="220" y="80" width="80" height="40" as="geometry"/></mxCell>
<mxCell id="o" value="obstacle" vertex="1" parent="1"><mxGeometry x="130" y="70" width="60" height="60" as="geometry"/></mxCell>
<mxCell id="e" value="contributes_to" edge="1" source="a" target="b" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
</root></mxGraphModel></diagram></mxfile>'''


class ApprovalReceiptConsumerTest(unittest.TestCase):
    def test_valid_receipt_accepts_only_disposition(self):
        f, w, r = accepted_case()
        report, _ = gate(current_finding=f, current_waiver=w, current_receipt=r)
        self.assertEqual((report["gateStatus"], report["decision"], report["risk"], report["verification"]), ("VALID", "ALLOW", "ACCEPTED", "PARTIAL"))
        self.assertEqual(report["findings"], [f])

    def test_mandatory_destructive_cases(self):
        cases = []

        def run(name, mutate, expected_code):
            f, w, r = accepted_case()
            p = policy()
            mutate(f, w, r, p)
            report, _ = gate(current_finding=f, current_waiver=w, current_receipt=r, current_policy=p)
            codes = {row["code"] for row in report["gateErrors"]}
            self.assertIn(expected_code, codes, (name, report))
            self.assertEqual((report["gateStatus"], report["decision"], report["risk"]), ("ERROR", "DENY", "OPEN"), name)
            cases.append(name)

        run("D01-free-form", lambda f,w,r,p: (w.__setitem__("approvalRef","review:1"), w.pop("approvalReceiptRef"), w.pop("approvalReceiptDigest")), "FREE_FORM_APPROVAL_REF_FORBIDDEN")
        run("D02-receipt-missing", lambda f,w,r,p: r.__setitem__("approval_id","other"), "APPROVAL_RECEIPT_MISSING")
        run("D03-digest", lambda f,w,r,p: w.__setitem__("approvalReceiptDigest","sha256:"+"0"*64), "APPROVAL_RECEIPT_DIGEST_MISMATCH")
        run("D04-invalid", lambda f,w,r,p: (r.__setitem__("status","INVALID"), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_NOT_VALID")
        run("D05-error", lambda f,w,r,p: (r.__setitem__("status","ERROR"), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_NOT_VALID")
        run("D06-candidate", lambda f,w,r,p: (r["subject"].__setitem__("candidate_revision","b"*40), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_CANDIDATE_MISMATCH")
        run("D07-finding", lambda f,w,r,p: (r["subject"].__setitem__("finding_digest","sha256:"+"0"*64), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_FINDING_MISMATCH")
        run("D08-subject", lambda f,w,r,p: w.__setitem__("subjectDigest","sha256:"+"0"*64), "waiver_invalid")
        run("D09-policy", lambda f,w,r,p: (r["subject"].__setitem__("policy_digest","sha256:"+"0"*64), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_POLICY_MISMATCH")
        run("D10-repository", lambda f,w,r,p: (r["subject"].__setitem__("repository","roccho-dev/ops"), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_REPOSITORY_MISMATCH")
        run("D11-action", lambda f,w,r,p: (r["action"].__setitem__("kind","pull_request_review.comment"), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_ACTION_NOT_ALLOWED")
        run("D12-scope", lambda f,w,r,p: (r["authority"].__setitem__("scope_digest",""), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_SCOPE_MISMATCH")
        run("D13-time", lambda f,w,r,p: (r["action"].__setitem__("submitted_at","2026-08-02T00:00:00+09:00"), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_TIME_MISMATCH")
        run("D14-engine", lambda f,w,r,p: (r.__setitem__("engine_manifest_digest","sha256:"+"0"*64), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_ENGINE_UNKNOWN")
        run("D15-other-finding", lambda f,w,r,p: (r["subject"].__setitem__("finding_digest","sha256:"+"a"*64), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_FINDING_MISMATCH")
        run("D16-unknown-receipt-field", lambda f,w,r,p: (r.__setitem__("provider_raw",{}), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_VALIDATION_EXCEPTION")
        run("D17-claim-overreach", lambda f,w,r,p: (r["claim_ceiling"].__setitem__("physical_human_identity_proven",True), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_SCOPE_MISMATCH")
        run("D18-action-state", lambda f,w,r,p: (r["action"].__setitem__("state","COMMENTED"), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_NOT_VALID")
        run("D19-receipt-id", lambda f,w,r,p: (r.__setitem__("approval_id","approval:other"), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_MISSING")
        run("D20-policy-change", lambda f,w,r,p: p.__setitem__("maxWaiverDays",7), "waiver_invalid")
        run("D21-version-only-engine", lambda f,w,r,p: (r.__setitem__("engine_manifest_digest","sha256:"+"8"*64), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_ENGINE_UNKNOWN")
        run("D22-unaccepted-action", lambda f,w,r,p: (r["action"].__setitem__("kind","diagram_waiver.approve"), w.__setitem__("approvalReceiptDigest",approval_receipt_digest(r))), "APPROVAL_RECEIPT_ACTION_NOT_ALLOWED")

        self.assertEqual(len(cases), 22)

    def test_no_provider_logic_or_free_form_acceptance_in_consumer(self):
        root = Path(__file__).resolve().parents[2] / "src" / "jsonl_diagram_core"
        text = "\n".join((root / name).read_text(encoding="utf-8") for name in ("approval_receipt.py", "policy_gate.py", "receipt_overlay.py"))
        for token in ("requests", "httpx", "github.Github", "urllib.request", "collaborator permission"):
            self.assertNotIn(token, text)
        self.assertNotIn("approvalRef", policy_gate_module._WAIVER_KEYS)
        self.assertIn("approvalReceiptRef", policy_gate_module._WAIVER_KEYS)
        self.assertIn("approvalReceiptDigest", policy_gate_module._WAIVER_KEYS)
        self.assertIn("FREE_FORM_APPROVAL_REF_FORBIDDEN", (root / "policy_gate.py").read_text(encoding="utf-8"))
        self.assertNotIn("diagram_waiver.approve", (root / "approval_receipt.py").read_text(encoding="utf-8"))
        self.assertNotIn("engine_digest", (root / "approval_receipt.py").read_text(encoding="utf-8"))

    def test_deterministic_gate_and_receipt_bound_overlay(self):
        semantic = semantic_crossing()
        geometry = inspect_semantic_drawio(semantic)
        current_finding = next(row for row in geometry["findings"] if row["ruleId"] == "edge_crosses_unrelated_rectangle")
        current_receipt = receipt(current_finding)
        current_waiver = waiver(current_finding, current_receipt)
        args = dict(
            semantic_model_digest=geometry["semanticModelDigest"],
            verification=geometry["verification"],
            findings=geometry["findings"],
            policy=policy(),
            waivers=[current_waiver],
            approval_receipts=[current_receipt],
            repository=REPOSITORY,
            candidate_revision=CANDIDATE,
            as_of=AS_OF,
        )
        first = gate_findings(**args)
        second = gate_findings(**copy.deepcopy(args))
        self.assertEqual(first, second)
        review, _ = project_review_drawio(semantic, first[0], first[1], as_of=AS_OF)
        self.assertIn('approvalReceiptRef="approval:1"', review)
        self.assertIn(f'approvalReceiptDigest="{approval_receipt_digest(current_receipt)}"', review)


if __name__ == "__main__":
    unittest.main()
