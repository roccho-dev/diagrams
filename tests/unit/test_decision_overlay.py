from __future__ import annotations

import unittest

from jsonl_diagram_core.decision_overlay import assert_semantic_drawio, inspect_semantic_drawio, project_review_drawio
from jsonl_diagram_core.policy_gate import gate_findings, policy_digest
from jsonl_diagram_core.quality import validate_drawio_quality


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


class DecisionOverlayTest(unittest.TestCase):
    def test_cleanish_diagram_is_partial_allow_clean(self):
        geometry = inspect_semantic_drawio(diagram())
        report, _ = gate_findings(semantic_model_digest=geometry["semanticModelDigest"], verification=geometry["verification"], findings=geometry["findings"], policy=policy(), waivers=[], as_of="2026-07-26T12:00:00+09:00")
        self.assertEqual((report["verification"], report["decision"], report["risk"]), ("PARTIAL", "ALLOW", "CLEAN"))

    def test_open_crossing_denies_and_projects(self):
        geometry = inspect_semantic_drawio(diagram(obstacle=True))
        report, gate_receipt = gate_findings(semantic_model_digest=geometry["semanticModelDigest"], verification=geometry["verification"], findings=geometry["findings"], policy=policy(), waivers=[], as_of="2026-07-26T12:00:00+09:00")
        self.assertEqual((report["decision"], report["risk"]), ("DENY", "OPEN"))
        review, projection = project_review_drawio(diagram(obstacle=True), report, gate_receipt, as_of="2026-07-26T12:00:00+09:00")
        self.assertIn("decision-overlay", review)
        self.assertGreater(projection["overlayCount"], 0)
        with self.assertRaisesRegex(ValueError, "review artifact"):
            assert_semantic_drawio(review)

    def test_exact_waiver_changes_only_disposition(self):
        semantic = diagram(obstacle=True)
        geometry = inspect_semantic_drawio(semantic)
        open_report, _ = gate_findings(semantic_model_digest=geometry["semanticModelDigest"], verification=geometry["verification"], findings=geometry["findings"], policy=policy(), waivers=[], as_of="2026-07-26T12:00:00+09:00")
        finding = next(f for f in geometry["findings"] if f["ruleId"] == "edge_crosses_unrelated_rectangle")
        waiver = {"schema":"DiagramWaiver.v1","waiverId":"W-1","findingKey":finding["findingKey"],"subjectDigest":finding["subjectDigest"],"findingDigest":finding["findingDigest"],"policyDigest":policy_digest(policy()),"reason":"bounded migration","evidenceRefs":["adrs#257"],"approvalRef":"review:1","issuedAt":"2026-07-26T10:00:00+09:00","expiresAt":"2026-08-01T10:00:00+09:00"}
        accepted, _ = gate_findings(semantic_model_digest=geometry["semanticModelDigest"], verification=geometry["verification"], findings=geometry["findings"], policy=policy(), waivers=[waiver], as_of="2026-07-26T12:00:00+09:00")
        self.assertEqual(open_report["findings"], accepted["findings"])
        self.assertEqual((accepted["decision"], accepted["risk"]), ("ALLOW", "ACCEPTED"))

    def test_projection_is_deterministic(self):
        semantic = diagram(obstacle=True)
        geometry = inspect_semantic_drawio(semantic)
        report, receipt = gate_findings(semantic_model_digest=geometry["semanticModelDigest"], verification=geometry["verification"], findings=geometry["findings"], policy=policy(), waivers=[], as_of="2026-07-26T12:00:00+09:00")
        a, ar = project_review_drawio(semantic, report, receipt, as_of="2026-07-26T12:00:00+09:00")
        b, br = project_review_drawio(semantic, report, receipt, as_of="2026-07-26T12:00:00+09:00")
        self.assertEqual(a, b)
        self.assertEqual(ar, br)

    def test_stale_waiver_fails_closed(self):
        geometry = inspect_semantic_drawio(diagram())
        waiver = {"schema":"DiagramWaiver.v1","waiverId":"W-stale","findingKey":"missing","subjectDigest":"x","findingDigest":"y","policyDigest":policy_digest(policy()),"reason":"x","evidenceRefs":["e"],"approvalRef":"a","issuedAt":"2026-07-26T10:00:00+09:00","expiresAt":"2026-08-01T10:00:00+09:00"}
        report, _ = gate_findings(semantic_model_digest=geometry["semanticModelDigest"], verification=geometry["verification"], findings=geometry["findings"], policy=policy(), waivers=[waiver], as_of="2026-07-26T12:00:00+09:00")
        self.assertEqual((report["gateStatus"], report["decision"]), ("ERROR", "DENY"))

    def test_quality_rejects_review_projection(self):
        semantic = diagram(obstacle=True)
        geometry = inspect_semantic_drawio(semantic)
        report, receipt = gate_findings(semantic_model_digest=geometry["semanticModelDigest"], verification=geometry["verification"], findings=geometry["findings"], policy=policy(), waivers=[], as_of="2026-07-26T12:00:00+09:00")
        review, _ = project_review_drawio(semantic, report, receipt, as_of="2026-07-26T12:00:00+09:00")
        with self.assertRaisesRegex(AssertionError, "review projection"):
            validate_drawio_quality(review)

    def test_expired_waiver_is_not_accepted(self):
        geometry = inspect_semantic_drawio(diagram(obstacle=True))
        finding = next(f for f in geometry["findings"] if f["ruleId"] == "edge_crosses_unrelated_rectangle")
        waiver = {"schema":"DiagramWaiver.v1","waiverId":"W-old","findingKey":finding["findingKey"],"subjectDigest":finding["subjectDigest"],"findingDigest":finding["findingDigest"],"policyDigest":policy_digest(policy()),"reason":"old","evidenceRefs":["e"],"approvalRef":"a","issuedAt":"2026-06-01T10:00:00+09:00","expiresAt":"2026-06-02T10:00:00+09:00"}
        report, _ = gate_findings(semantic_model_digest=geometry["semanticModelDigest"], verification=geometry["verification"], findings=geometry["findings"], policy=policy(), waivers=[waiver], as_of="2026-07-26T12:00:00+09:00")
        self.assertEqual((report["gateStatus"], report["decision"], report["risk"]), ("ERROR", "DENY", "OPEN"))

    def test_label_cannot_self_waive(self):
        semantic = diagram(obstacle=True).replace('value="obstacle"', 'value="ACCEPTED W-FAKE"')
        geometry = inspect_semantic_drawio(semantic)
        report, _ = gate_findings(semantic_model_digest=geometry["semanticModelDigest"], verification=geometry["verification"], findings=geometry["findings"], policy=policy(), waivers=[], as_of="2026-07-26T12:00:00+09:00")
        self.assertEqual((report["decision"], report["risk"]), ("DENY", "OPEN"))

    def test_policy_change_invalidates_waiver(self):
        geometry = inspect_semantic_drawio(diagram(obstacle=True))
        finding = next(f for f in geometry["findings"] if f["ruleId"] == "edge_crosses_unrelated_rectangle")
        old_policy = policy()
        waiver = {"schema":"DiagramWaiver.v1","waiverId":"W-1","findingKey":finding["findingKey"],"subjectDigest":finding["subjectDigest"],"findingDigest":finding["findingDigest"],"policyDigest":policy_digest(old_policy),"reason":"bounded migration","evidenceRefs":["e"],"approvalRef":"a","issuedAt":"2026-07-26T10:00:00+09:00","expiresAt":"2026-08-01T10:00:00+09:00"}
        changed = policy()
        changed["maxWaiverDays"] = 7
        report, _ = gate_findings(semantic_model_digest=geometry["semanticModelDigest"], verification=geometry["verification"], findings=geometry["findings"], policy=changed, waivers=[waiver], as_of="2026-07-26T12:00:00+09:00")
        self.assertEqual((report["gateStatus"], report["decision"]), ("ERROR", "DENY"))


if __name__ == "__main__":
    unittest.main()
