from __future__ import annotations

import copy
import unittest

from jsonl_diagram_core.render_audit import evaluate_render_audit, receipt_bytes, sha256_json

SOURCE_SHA = "sha256:" + "1" * 64
SEMANTIC_SHA = "sha256:" + "2" * 64
DIGEST = "sha256:" + "3" * 64


def policy():
    return {
        "kind": "diagram.renderAuditPolicy.v1",
        "asOf": "2026-07-29T08:00:00+09:00",
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
        "requiredEdges": [{"id": "flow", "relatedSubjects": ["scope"]}],
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
        "renderer": {"product": "draw.io GraphViewer", "version": "30.0.4", "sha256": DIGEST},
        "container": {"digest": "mcr.microsoft.com/x@sha256:abc", "osReleaseSha256": DIGEST},
        "browser": {"version": "145", "executableSha256": DIGEST},
        "font": {"family": "WenQuanYi Zen Hei", "sha256": DIGEST},
        "viewport": {"width": 1280, "height": 800, "devicePixelRatio": 1},
        "theme": "light",
    }


def subject(bounds, label):
    return {
        "present": True,
        "exactness": "renderer-exact",
        "bounds": list(bounds),
        "labelBounds": list(label),
        "clipBounds": list(bounds),
        "labelOcclusionFraction": 0.0,
        "subjectOcclusionFraction": 0.0,
        "textColor": "rgb(0, 0, 0)",
        "backgroundColor": "rgb(255, 255, 255)",
    }


def observation():
    return {
        "kind": "diagram.renderObservations.v1",
        "sourceMxfileSha256": SOURCE_SHA,
        "semanticDigest": SEMANTIC_SHA,
        "semanticStatus": "PASS",
        "pageIds": ["semantic-contract-v1"],
        "initialized": True,
        "svgCount": 1,
        "sourceModelUnchanged": True,
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


class RenderAuditTests(unittest.TestCase):
    def test_clean_baseline(self):
        a = observation()
        receipt = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        self.assertEqual(receipt["result"]["verification"], "COMPLETE")
        self.assertEqual(receipt["result"]["decision"], "ALLOW")
        self.assertEqual(receipt["result"]["risk"], "CLEAN")
        self.assertEqual(receipt["result"]["findings"], [])
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
        self.assertIn("EDGE_CROSSES_LABEL", {item["code"] for item in receipt["result"]["findings"]})
        self.assertEqual(receipt["result"]["decision"], "DENY")

    def test_waiver_preserves_findings(self):
        a = observation()
        a["subjects"]["scope"]["labelBounds"] = [390, 195, 60, 25]
        base = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        finding = next(item for item in base["result"]["findings"] if item["code"] == "EDGE_CROSSES_LABEL")
        waiver = {
            "kind": "diagram.renderWaiver.v1",
            "findingKey": sha256_json(finding),
            "factsSha256": base["facts_sha256"],
            "approvalRef": "adrs#x",
            "expires": "2026-08-01",
        }
        accepted = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime(), waivers=[waiver])
        self.assertEqual(accepted["result"]["findings"], base["result"]["findings"])
        self.assertEqual(accepted["result"]["decision"], "ALLOW")
        self.assertEqual(accepted["result"]["risk"], "ACCEPTED")

    def test_semantic_contamination_is_error(self):
        a = observation()
        a["semanticDigest"] = DIGEST
        receipt = evaluate_render_audit(a, copy.deepcopy(a), policy(), runtime())
        self.assertEqual(receipt["result"]["verification"], "ERROR")
        self.assertIn("SEMANTIC_CHANNEL_CONTAMINATED", {item["code"] for item in receipt["result"]["findings"]})


if __name__ == "__main__":
    unittest.main()
