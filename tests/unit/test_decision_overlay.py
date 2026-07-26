from __future__ import annotations

import unittest

from jsonl_diagram_core.approval_receipt import approval_receipt_digest
from jsonl_diagram_core.decision_overlay import assert_semantic_drawio, inspect_semantic_drawio, project_review_drawio
from jsonl_diagram_core.policy_gate import gate_findings, policy_digest
from jsonl_diagram_core.quality import validate_drawio_quality

REPOSITORY = "roccho-dev/diagrams"
CANDIDATE = "a" * 40
AS_OF = "2026-07-26T12:00:00+09:00"


def diagram(*, obstacle: bool = False) -> str:
    extra = '<mxCell id="o" value="obstacle" vertex="1" parent="1"><mxGeometry x="130" y="70" width="60" height="60" as="geometry"/></mxCell>' if obstacle else ''
    return f'''<mxfile><diagram id="p1" name="P1"><mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="a" value="A" vertex="1" parent="1"><mxGeometry x="20" y="80" width="80" height="40" as="geometry"/></mxCell>
<mxCell id="b" value="B" vertex="1" parent="1"><mxGeometry x="220" y="80" width="80" height="40" as="geometry"/></mxCell>
{extra}<mxCell id="e" value="contributes_to" edge="1" source="a" target="b" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
</root></mxGraphModel></diagram></mxfile>'''


def policy() -> dict:
    return {"schema":"DiagramPolicy.v1","maxWaiverDays":31,"rules":{
        "partial_overlap":{"effect":"INFO","waivable":False},
        "model_parent_not_containing":{"effect":"DENY","waivable":True},
        "edge_route_approximate":{"effect":"INFO","waivable":False},
        "edge_crosses_unrelated_rectangle":{"effect":"DENY","waivable":True},
    }}


def approval_receipt(finding: dict, *, status: str = "VALID") -> dict:
    receipt = {
        "kind":"approvalReceipt.v1",
        "approval_id":"approval:W-1",
        "subject":{
            "repository":REPOSITORY,
            "candidate_revision":CANDIDATE,
            "finding_digest":finding["findingDigest"],
            "policy_digest":policy_digest(policy()),
        },
        "actor":{
            "subject_id":"role:diagram-approver",
            "provider":"github",
            "provider_account_id":40359643,
            "provider_login":"roccho-dev",
        },
        "action":{
            "kind":"pull_request_review.approve",
            "provider_review_id":9001,
            "state":"APPROVED",
            "submitted_at":"2026-07-26T10:30:00+09:00",
        },
        "authority":{
            "grant_id":"G-1",
            "scope_digest":"sha256:" + "1" * 64,
            "valid_from":"2026-07-01T00:00:00+09:00",
            "valid_until":"2026-08-01T00:00:00+09:00",
        },
        "provider_evidence_digest":"sha256:" + "2" * 64,
        "engine_digest":"sha256:" + "3" * 64,
        "as_of":"2026-07-26T10:31:00+09:00",
        "status":status,
        "findings":[],
        "claim_ceiling":{
            "physical_human_identity_proven":False,
            "account_non_compromise_proven":False,
            "provider_independent_non_repudiation_proven":False,
        },
    }
    return receipt


def exact_waiver(finding: dict, receipt: dict) -> dict:
    return {
        "schema":"DiagramWaiver.v1",
        "waiverId":"W-1",
        "findingKey":finding["findingKey"],
        "subjectDigest":finding["subjectDigest"],
        "findingDigest":finding["findingDigest"],
        "policyDigest":policy_digest(policy()),
        "reason":"bounded migration",
        "evidenceRefs":["adrs#257"],
        "approvalReceiptRef":receipt["approval_id"],
        "approvalReceiptDigest":approval_receipt_digest(receipt),
        "issuedAt":"2026-07-26T10:00:00+09:00",
        "expiresAt":"2026-08-01T10:00:00+09:00",
    }


def gate(geometry: dict, *, waivers: list[dict] | None = None, receipts: list[dict] | None = None, current_policy: dict | None = None):
    return gate_findings(
        semantic_model_digest=geometry["semanticModelDigest"],
        verification=geometry["verification"],
        findings=geometry["findings"],
        policy=current_policy or policy(),
        waivers=waivers or [],
        approval_receipts=receipts or [],
        repository=REPOSITORY,
        candidate_revision=CANDIDATE,
        as_of=AS_OF,
    )


class DecisionOverlayTest(unittest.TestCase):
    def test_cleanish_diagram_is_partial_allow_clean(self):
        geometry = inspect_semantic_drawio(diagram())
        report, _ = gate(geometry)
        self.assertEqual((report["verification"], report["decision"], report["risk"]), ("PARTIAL", "ALLOW", "CLEAN"))

    def test_open_crossing_denies_and_projects(self):
        geometry = inspect_semantic_drawio(diagram(obstacle=True))
        report, gate_receipt = gate(geometry)
        self.assertEqual((report["decision"], report["risk"]), ("DENY", "OPEN"))
        review, projection = project_review_drawio(diagram(obstacle=True), report, gate_receipt, as_of=AS_OF)
        self.assertIn("decision-overlay", review)
        self.assertGreater(projection["overlayCount"], 0)
        with self.assertRaisesRegex(ValueError, "review artifact"):
            assert_semantic_drawio(review)

    def test_exact_waiver_changes_only_disposition(self):
        semantic = diagram(obstacle=True)
        geometry = inspect_semantic_drawio(semantic)
        open_report, _ = gate(geometry)
        finding = next(f for f in geometry["findings"] if f["ruleId"] == "edge_crosses_unrelated_rectangle")
        receipt = approval_receipt(finding)
        accepted, gate_receipt = gate(geometry, waivers=[exact_waiver(finding, receipt)], receipts=[receipt])
        self.assertEqual(open_report["findings"], accepted["findings"])
        self.assertEqual((accepted["verification"], accepted["decision"], accepted["risk"]), ("PARTIAL", "ALLOW", "ACCEPTED"))
        self.assertEqual(accepted["usedApprovalReceiptRefs"], [receipt["approval_id"]])
        self.assertIn("approvalReceiptsDigest", gate_receipt)

    def test_projection_is_deterministic(self):
        semantic = diagram(obstacle=True)
        geometry = inspect_semantic_drawio(semantic)
        report, receipt = gate(geometry)
        a, ar = project_review_drawio(semantic, report, receipt, as_of=AS_OF)
        b, br = project_review_drawio(semantic, report, receipt, as_of=AS_OF)
        self.assertEqual(a, b)
        self.assertEqual(ar, br)

    def test_stale_waiver_fails_closed(self):
        geometry = inspect_semantic_drawio(diagram())
        waiver = {"schema":"DiagramWaiver.v1","waiverId":"W-stale","findingKey":"missing","subjectDigest":"x","findingDigest":"y","policyDigest":policy_digest(policy()),"reason":"x","evidenceRefs":["e"],"approvalReceiptRef":"approval:missing","approvalReceiptDigest":"sha256:"+"0"*64,"issuedAt":"2026-07-26T10:00:00+09:00","expiresAt":"2026-08-01T10:00:00+09:00"}
        report, _ = gate(geometry, waivers=[waiver])
        self.assertEqual((report["gateStatus"], report["decision"]), ("ERROR", "DENY"))

    def test_quality_rejects_review_projection(self):
        semantic = diagram(obstacle=True)
        geometry = inspect_semantic_drawio(semantic)
        report, receipt = gate(geometry)
        review, _ = project_review_drawio(semantic, report, receipt, as_of=AS_OF)
        with self.assertRaisesRegex(AssertionError, "review projection"):
            validate_drawio_quality(review)

    def test_expired_waiver_is_not_accepted(self):
        geometry = inspect_semantic_drawio(diagram(obstacle=True))
        finding = next(f for f in geometry["findings"] if f["ruleId"] == "edge_crosses_unrelated_rectangle")
        receipt = approval_receipt(finding)
        waiver = exact_waiver(finding, receipt)
        waiver["issuedAt"] = "2026-06-01T10:00:00+09:00"
        waiver["expiresAt"] = "2026-06-02T10:00:00+09:00"
        report, _ = gate(geometry, waivers=[waiver], receipts=[receipt])
        self.assertEqual((report["gateStatus"], report["decision"], report["risk"]), ("ERROR", "DENY", "OPEN"))

    def test_label_cannot_self_waive(self):
        semantic = diagram(obstacle=True).replace('value="obstacle"', 'value="ACCEPTED W-FAKE"')
        geometry = inspect_semantic_drawio(semantic)
        report, _ = gate(geometry)
        self.assertEqual((report["decision"], report["risk"]), ("DENY", "OPEN"))

    def test_policy_change_invalidates_waiver(self):
        geometry = inspect_semantic_drawio(diagram(obstacle=True))
        finding = next(f for f in geometry["findings"] if f["ruleId"] == "edge_crosses_unrelated_rectangle")
        receipt = approval_receipt(finding)
        waiver = exact_waiver(finding, receipt)
        changed = policy()
        changed["maxWaiverDays"] = 7
        report, _ = gate(geometry, waivers=[waiver], receipts=[receipt], current_policy=changed)
        self.assertEqual((report["gateStatus"], report["decision"]), ("ERROR", "DENY"))

    def test_free_form_approval_ref_is_rejected(self):
        geometry = inspect_semantic_drawio(diagram(obstacle=True))
        finding = next(f for f in geometry["findings"] if f["ruleId"] == "edge_crosses_unrelated_rectangle")
        waiver = exact_waiver(finding, approval_receipt(finding))
        waiver.pop("approvalReceiptRef")
        waiver.pop("approvalReceiptDigest")
        waiver["approvalRef"] = "review:1"
        report, _ = gate(geometry, waivers=[waiver])
        self.assertIn("FREE_FORM_APPROVAL_REF_FORBIDDEN", {row["code"] for row in report["gateErrors"]})
        self.assertEqual((report["gateStatus"], report["decision"], report["risk"]), ("ERROR", "DENY", "OPEN"))


if __name__ == "__main__":
    unittest.main()
