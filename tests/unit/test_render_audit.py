from __future__ import annotations

import copy
import unittest

from jsonl_diagram_core.render_audit import evaluate_render_audit, receipt_bytes, sha256_json

SOURCE_SHA = "sha256:" + "1" * 64
SEMANTIC_SHA = "sha256:" + "2" * 64
DIGEST = "sha256:" + "3" * 64
MODEL_DIGEST = "sha256:" + "4" * 64


def policy():
    return {
        "kind": "diagram.renderAuditPolicy.v1",
        "asOf": "2026-07-29T08:00:00+09:00",
        "waiverMaximumDays": 31,
        "source": {
            "adrsMergeCommit": "e2b2251160b4178f51fc00392d8e3a5dd686b4ad",
            "decisionId": "01KZV5A1C0RRECT10N00000200",
            "releaseId": "diagram-semantic-contract-v1.0.2",
            "mxfileSha256": SOURCE_SHA,
            "semanticDigest": SEMANTIC_SHA,
            "pageIds": ["semantic-contract-v1"],
        },
        "requiredSubjects": [
            {"id": "scope", "labelInsideSubject": True},
            {"id": "input", "labelInsideSubject": True},
            {"id": "output", "labelInsideSubject": True},
        ],
        "requiredEdges": [{"id": "flow", "source": "input", "target": "output", "relatedSubjects": ["scope"]}],
        "protectedLabels": ["scope", "input", "output"],
        "protectedSubjects": ["scope", "input", "output"],
        "labelTolerance": 0.5,
        "edgeClearance": 0.0,
        "minContrastRatio": 4.5,
        "fullyOccludedAt": 0.99,
        "unsupportedExactness": "ERROR",
    }


def runtime():
    return {
        "kind": "diagram.renderAuditRuntimePin.v2",
        "renderer": {
            "product": "draw.io GraphViewer",
            "repository": "jgraph/drawio",
            "tag": "v30.0.4",
            "version": "30.0.4",
            "commit": "a" * 40,
            "sha256": DIGEST,
            "licenseSha256": DIGEST,
        },
        "container": {
            "digest": "mcr.microsoft.com/x@sha256:" + "b" * 64,
            "tag": "mcr.microsoft.com/x:v1",
            "osReleaseSha256": DIGEST,
        },
        "browser": {"path": "/browser", "version": "145", "executableSha256": DIGEST},
        "font": {"family": "WenQuanYi Zen Hei", "path": "/font", "sha256": DIGEST},
        "playwrightPython": {"version": "1.58.0", "wheelSha256": DIGEST, "dependencyWheelSha256": [DIGEST]},
        "viewport": {"width": 1280, "height": 800, "devicePixelRatio": 1},
        "theme": "light",
    }


def subject(bounds, label):
    return {
        "present": True,
        "labelPresent": True,
        "exactness": "renderer-exact",
        "bounds": list(bounds),
        "labelBounds": list(label),
        "clipBounds": list(bounds),
        "labelOcclusionFraction": 0.0,
        "subjectOcclusionFraction": 0.0,
        "textColor": "rgb(0, 0, 0)",
        "backgroundColor": "rgb(255, 255, 255)",
        "fontFamily": "WenQuanYi Zen Hei",
    }


def observation():
    rt = runtime()
    return {
        "kind": "diagram.renderObservations.v1",
        "sourceMxfileSha256": SOURCE_SHA,
        "semanticDigest": SEMANTIC_SHA,
        "semanticStatus": "PASS",
        "pageIds": ["semantic-contract-v1"],
        "initialized": True,
        "svgCount": 1,
        "modelBeforeSha256": MODEL_DIGEST,
        "modelAfterSha256": MODEL_DIGEST,
        "sourceModelUnchanged": True,
        "runtimeObserved": {
            "browserVersion": rt["browser"]["version"],
            "browserExecutableSha256": rt["browser"]["executableSha256"],
            "osReleaseSha256": rt["container"]["osReleaseSha256"],
            "fontSha256": rt["font"]["sha256"],
            "fontLoaded": True,
            "viewport": rt["viewport"],
            "theme": rt["theme"],
        },
        "externalRequests": [],
        "consoleErrors": [],
        "pageErrors": [],
        "unsupported": [],
        "duplicateRenderStatePaths": [],
        "subjects": {
            "scope": subject((80, 80, 760, 260), (92, 90, 40, 18)),
            "input": subject((180, 180, 150, 60), (235, 200, 40, 18)),
            "output": subject((520, 180, 150, 60), (568, 200, 50, 18)),
        },
        "edges": {
            "flow": {
                "present": True,
                "exactness": "renderer-exact",
                "source": "input",
                "target": "output",
                "points": [[330, 210], [520, 210]],
            }
        },
        "screenshot": {"sha256": DIGEST, "byteLength": 1000, "nonEmpty": True},
    }


def finding_codes(receipt):
    return {item["code"] for item in receipt["result"]["findings"]}


class RenderAuditTests(unittest.TestCase):
    def test_clean_baseline(self):
        a = observation()
        receipt = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        self.assertEqual(receipt["result"]["verification"], "COMPLETE")
        self.assertEqual(receipt["result"]["decision"], "ALLOW")
        self.assertEqual(receipt["result"]["risk"], "CLEAN")
        self.assertEqual(receipt["result"]["findings"], [])
        self.assertTrue(receipt["auditExecutionComplete"])
        self.assertTrue(receipt["renderQualityAuditComplete"])

    def test_deterministic_receipt(self):
        a = observation()
        first = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        second = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        self.assertEqual(receipt_bytes(first), receipt_bytes(second))

    def test_edge_crosses_label(self):
        a = observation()
        a["subjects"]["scope"]["labelBounds"] = [390, 195, 60, 25]
        receipt = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        self.assertIn("EDGE_CROSSES_LABEL", finding_codes(receipt))
        self.assertEqual(receipt["result"]["decision"], "DENY")

    def test_exact_waiver_preserves_findings_only(self):
        a = observation()
        a["subjects"]["scope"]["labelBounds"] = [390, 195, 60, 25]
        base = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        finding = next(item for item in base["result"]["findings"] if item["code"] == "EDGE_CROSSES_LABEL")
        waiver = {
            "kind": "diagram.renderWaiver.v1",
            "findingKey": sha256_json(finding),
            "factsSha256": base["facts_sha256"],
            "approvalRef": "adrs#accepted",
            "issuedAt": "2026-07-29T07:00:00+09:00",
            "expires": "2026-08-01T08:00:00+09:00",
        }
        accepted = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime(), waivers=[waiver])
        self.assertEqual(accepted["result"]["findings"], base["result"]["findings"])
        self.assertEqual(accepted["result"]["decision"], "ALLOW")
        self.assertEqual(accepted["result"]["risk"], "ACCEPTED")

    def test_expired_waiver_fails_closed(self):
        a = observation()
        a["subjects"]["scope"]["labelBounds"] = [390, 195, 60, 25]
        base = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        finding = next(item for item in base["result"]["findings"] if item["code"] == "EDGE_CROSSES_LABEL")
        waiver = {
            "kind": "diagram.renderWaiver.v1",
            "findingKey": sha256_json(finding),
            "factsSha256": base["facts_sha256"],
            "approvalRef": "adrs#expired",
            "issuedAt": "2026-07-01T00:00:00+09:00",
            "expires": "2026-07-02T00:00:00+09:00",
        }
        receipt = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime(), waivers=[waiver])
        self.assertIn("WAIVER_CHANGED_OBSERVATION", finding_codes(receipt))
        self.assertEqual(receipt["result"]["gateStatus"], "ERROR")

    def test_integrity_finding_cannot_be_waived(self):
        a = observation()
        a["semanticDigest"] = DIGEST
        base = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        finding = next(item for item in base["result"]["findings"] if item["code"] == "SEMANTIC_CHANNEL_CONTAMINATED")
        waiver = {
            "kind": "diagram.renderWaiver.v1",
            "findingKey": sha256_json(finding),
            "factsSha256": base["facts_sha256"],
            "approvalRef": "adrs#invalid",
            "issuedAt": "2026-07-29T07:00:00+09:00",
            "expires": "2026-08-01T08:00:00+09:00",
        }
        receipt = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime(), waivers=[waiver])
        self.assertIn("WAIVER_CHANGED_OBSERVATION", finding_codes(receipt))
        self.assertEqual(receipt["result"]["gateStatus"], "ERROR")

    def test_model_exact_is_not_renderer_exact(self):
        a = observation()
        a["subjects"]["input"]["exactness"] = "model-exact"
        receipt = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        self.assertIn("UNSUPPORTED_RENDER_EXACTNESS", finding_codes(receipt))
        self.assertEqual(receipt["result"]["verification"], "ERROR")

    def test_actual_font_must_match_pin(self):
        a = observation()
        a["subjects"]["input"]["fontFamily"] = "Arial"
        receipt = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        self.assertIn("FONT_OR_VIEWPORT_IDENTITY_MISSING", finding_codes(receipt))
        self.assertEqual(receipt["result"]["verification"], "ERROR")

    def test_semantic_contamination_is_error(self):
        a = observation()
        a["semanticDigest"] = DIGEST
        receipt = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        self.assertEqual(receipt["result"]["verification"], "ERROR")
        self.assertIn("SEMANTIC_CHANNEL_CONTAMINATED", finding_codes(receipt))


if __name__ == "__main__":
    unittest.main()
