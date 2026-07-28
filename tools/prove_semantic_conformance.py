#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

from jsonl_diagram_core.mxgraph_model import build_model
from jsonl_diagram_core.semantic_conformance import (
    compare_semantics,
    parse_mxfile,
    receipt_bytes,
    semantic_selection,
    sha256_bytes,
    sha256_json,
)

Json = dict[str, object]


def read_events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def provenance(xml: bytes, revision: str, generated_at: str, root: Path) -> Json:
    events = (root / "tests/fixtures/semantic_conformance/observed.events.jsonl").read_bytes()
    generator = (root / "src/jsonl_diagram_core/mxgraph_model.py").read_bytes()
    return {
        "kind": "diagram.observedProvenance.v1",
        "implementationRevision": revision,
        "implementationSourceDigest": sha256_json({"revision": revision, "events": sha256_bytes(events), "generator": sha256_bytes(generator)}),
        "generatorDigest": sha256_bytes(generator),
        "generatedArtifactSha256": sha256_bytes(xml),
        "generatedAt": generated_at,
        "origin": "implementation-derived",
        "expectedContentSourceUsed": False,
    }


def replace_once(data: bytes, old: bytes, new: bytes) -> bytes:
    if data.count(old) < 1:
        raise AssertionError(f"expected occurrence of {old!r}")
    return data.replace(old, new, 1)


def with_contract(expected: bytes, base: Json, policy: Json) -> Json:
    contract = copy.deepcopy(base)
    contract["policy"] = policy
    contract["policyCanonicalDigest"] = sha256_json(policy)
    contract["acceptedArtifactSha256"] = sha256_bytes(expected)
    pages = parse_mxfile(expected)
    contract["expectedSemanticSha256"] = sha256_json(semantic_selection(pages, policy))
    contract["pageIds"] = sorted(pages)
    contract["stableSubjectIds"] = sorted(f"{pid}:{sid}" for pid, page in pages.items() for sid in page.subjects)
    return contract


def status_and_codes(receipt: Json) -> tuple[str, set[str]]:
    comparison = receipt["comparison"]
    codes = {item["code"] for key in ("missing", "additional", "changed", "errors") for item in comparison.get(key, [])}
    return str(comparison["status"]), codes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--implementation-revision", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    expected = (root / "tests/fixtures/semantic_conformance/expected.drawio").read_bytes()
    contract: Json = json.loads((root / "tests/fixtures/semantic_conformance/expected-contract.json").read_text(encoding="utf-8"))
    events = read_events(root / "tests/fixtures/semantic_conformance/observed.events.jsonl")
    observed = build_model(events).encode("utf-8")
    base_provenance = provenance(observed, args.implementation_revision, args.generated_at, root)

    baseline = compare_semantics(expected, observed, contract, base_provenance)
    if baseline["comparison"]["status"] != "PASS":
        raise AssertionError("baseline conformance must pass")

    cases: list[tuple[str, str, str, Callable[[], Json]]] = []

    def run(e: bytes = expected, o: bytes = observed, c: Json | None = None, p: Json | None = None) -> Json:
        prov = copy.deepcopy(p or base_provenance)
        prov["generatedArtifactSha256"] = sha256_bytes(o)
        return compare_semantics(e, o, copy.deepcopy(c or contract), prov)

    cases.append(("D01-missing-expected", "FAIL", "missing_expected", lambda: run(o=replace_once(observed, b' jsonlId="output"', b' jsonlId="output-missing"'))))
    extra = replace_once(observed, b"</root>", b'<object id="extra" label="Extra" jsonlType="node" jsonlId="extra" semanticKind="process" metaJson="{}"><mxCell vertex="1" parent="1"><mxGeometry x="10" y="10" width="10" height="10" as="geometry"/></mxCell></object></root>')
    cases.append(("D02-unapproved-observed", "FAIL", "unapproved_observed", lambda: run(o=extra)))
    cases.append(("D03-tree-parent", "FAIL", "tree_changed", lambda: run(o=replace_once(observed, b'semanticGroup="scope"', b'semanticGroup="other"'))))
    cases.append(("D04-edge-target", "FAIL", "graph_changed", lambda: run(o=replace_once(observed, b'semanticTarget="output"', b'semanticTarget="input"'))))
    reversed_edge = replace_once(replace_once(observed, b'semanticSource="input"', b'semanticSource="__tmp__"'), b'semanticTarget="output"', b'semanticTarget="input"').replace(b'semanticSource="__tmp__"', b'semanticSource="output"')
    cases.append(("D05-edge-direction", "FAIL", "graph_changed", lambda: run(o=reversed_edge)))
    cases.append(("D06-relation-kind", "FAIL", "graph_changed", lambda: run(o=replace_once(observed, b'semanticKind="produces"', b'semanticKind="depends_on"'))))

    spatial_policy = {"kind": "diagram.semanticComparisonPolicy.v1", "pageIds": ["semantic-contract-v1"], "pageOrderSemantic": False, "semanticChannels": ["identity", "tree", "graph", "overlay"], "implicitToleranceAllowed": False, "spatialRules": [{"pageId": "semantic-contract-v1", "a": "scope", "b": "input", "relation": "contains", "tolerance": 0.0}], "visualIsolation": True}
    spatial_contract = with_contract(expected, contract, spatial_policy)
    moved_out = replace_once(expected, b'x="100" y="100" width="150"', b'x="900" y="100" width="150"')
    cases.append(("D07-containment-to-overlap", "FAIL", "spatial_relation_changed", lambda: run(o=moved_out, c=spatial_contract, p=provenance(moved_out, args.implementation_revision, args.generated_at, root))))
    ratio_policy = {"kind": "diagram.semanticComparisonPolicy.v1", "pageIds": ["semantic-contract-v1"], "pageOrderSemantic": False, "semanticChannels": ["identity", "tree", "graph", "overlay"], "implicitToleranceAllowed": False, "spatialRules": [{"pageId": "semantic-contract-v1", "a": "scope", "b": "input", "relation": "contains", "tolerance": 0.001}], "visualIsolation": True}
    ratio_contract = with_contract(expected, contract, ratio_policy)
    resized = replace_once(expected, b'x="100" y="100" width="150" height="60"', b'x="100" y="100" width="240" height="60"')
    cases.append(("D08-overlap-ratio", "FAIL", "overlap_ratio_changed", lambda: run(o=resized, c=ratio_contract, p=provenance(resized, args.implementation_revision, args.generated_at, root))))
    cases.append(("D09-visual-only", "PASS", "visual_only_changed", lambda: run()))
    annotation = replace_once(observed, b"</root>", b'<mxCell id="annotation" value="note" vertex="1" parent="1"><mxGeometry x="5" y="5" width="20" height="10" as="geometry"/></mxCell></root>')
    cases.append(("D10-annotation-ignored", "PASS", "", lambda: run(o=annotation)))
    duplicate = replace_once(observed, b"</root>", b'<object id="dup" label="Input duplicate" jsonlType="node" jsonlId="input" semanticKind="process" metaJson="{}"><mxCell vertex="1" parent="1"><mxGeometry x="5" y="5" width="20" height="10" as="geometry"/></mxCell></object></root>')
    cases.append(("D11-duplicate-subject", "ERROR", "DUPLICATE_IDENTITY", lambda: run(o=duplicate)))
    root_xml = ET.fromstring(observed)
    root_xml.append(copy.deepcopy(next(iter(root_xml))))
    duplicate_page = ET.tostring(root_xml, encoding="utf-8")
    cases.append(("D12-duplicate-page", "ERROR", "DUPLICATE_PAGE_ID", lambda: run(o=duplicate_page)))
    bad_digest = copy.deepcopy(contract); bad_digest["acceptedArtifactSha256"] = "sha256:" + "0" * 64
    cases.append(("D13-expected-digest", "ERROR", "EXPECTED_ARTIFACT_DIGEST_MISMATCH", lambda: run(c=bad_digest)))
    missing_rev = copy.deepcopy(base_provenance); missing_rev.pop("implementationRevision")
    cases.append(("D14-observed-revision", "ERROR", "MISSING_PROVENANCE", lambda: run(p=missing_rev)))
    reused = copy.deepcopy(base_provenance); reused["expectedContentSourceUsed"] = True
    cases.append(("D15-expected-source-reused", "ERROR", "EXPECTED_CONTENT_SOURCE_REUSED", lambda: run(p=reused)))
    cases.append(("D16-malformed-xml", "ERROR", "MALFORMED_INPUT", lambda: run(o=b"<mxfile>")))
    rotated = replace_once(expected, b'<mxCell vertex="1" parent="group_scope" style="shape=rectangle;rounded=0;whiteSpace=wrap;html=1;">', b'<mxCell vertex="1" parent="group_scope" style="shape=rectangle;rotation=45;">')
    cases.append(("D17-unsupported-exactness", "ERROR", "UNSUPPORTED_GEOMETRY", lambda: run(e=expected, o=rotated, c=spatial_contract, p=provenance(rotated, args.implementation_revision, args.generated_at, root))))
    exception_contract = copy.deepcopy(contract); exception_contract["pageIds"] = [{"not": "sortable"}, None]
    cases.append(("D18-comparator-exception", "ERROR", "COMPARATOR_EXCEPTION", lambda: run(c=exception_contract)))
    expected_overlay = replace_once(expected, b"</root>", b'<object id="overlay" label="accepted" jsonlType="overlay" jsonlId="overlay-1" semanticKind="decision" semanticSubject="flow" semanticState="accepted" semanticExpiry="2026-08-31" decisionRef="roccho-dev/adrs#257" metaJson="{}"><mxCell vertex="1" parent="1"><mxGeometry x="1" y="1" width="1" height="1" as="geometry"/></mxCell></object></root>')
    observed_overlay = replace_once(expected_overlay, b'semanticState="accepted"', b'semanticState="open"')
    overlay_contract = with_contract(expected_overlay, contract, contract["policy"])
    cases.append(("D19-overlay-changed", "FAIL", "overlay_changed", lambda: run(e=expected_overlay, o=observed_overlay, c=overlay_contract, p=provenance(observed_overlay, args.implementation_revision, args.generated_at, root))))
    cases.append(("D20-deterministic-receipt", "PASS", "", lambda: run()))

    matrix = []
    for name, expected_status, expected_code, callback in cases:
        first = callback()
        second = callback()
        status, codes = status_and_codes(first)
        deterministic = receipt_bytes(first) == receipt_bytes(second)
        code_ok = expected_code == "" or expected_code in codes or (expected_code == "visual_only_changed" and bool(first["comparison"].get("visual_only")))
        passed = status == expected_status and code_ok and deterministic
        matrix.append({"case": name, "status": "PASS" if passed else "FAIL", "observedStatus": status, "expectedStatus": expected_status, "codes": sorted(codes), "expectedCode": expected_code, "deterministic": deterministic})
    if not all(row["status"] == "PASS" for row in matrix):
        raise AssertionError(json.dumps(matrix, indent=2))

    result = {
        "kind": "diagramSemanticConformanceProof.v1",
        "status": "PASS",
        "implementationRevision": args.implementation_revision,
        "baselineReceipt": baseline,
        "baselineReceiptSha256": sha256_bytes(receipt_bytes(baseline)),
        "destructiveCaseCount": len(matrix),
        "destructiveCases": matrix,
        "comparisonIrPersisted": False,
        "authority": False,
        "renderQualityProven": False,
        "publicationAdmissible": False,
        "businessOutcomeAchieved": False,
        "corporateSaleOutcomeAchieved": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
