#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Callable

from jsonl_diagram_core.render_audit import evaluate_render_audit, receipt_bytes, sha256_json

Json = dict[str, object]


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def codes(receipt: dict[str, object]) -> set[str]:
    result = receipt.get("result")
    if not isinstance(result, dict):
        return set()
    findings = result.get("findings")
    if not isinstance(findings, list):
        return set()
    return {str(item.get("code")) for item in findings if isinstance(item, dict)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations-a", type=Path, required=True)
    parser.add_argument("--observations-b", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    base_a = load(args.observations_a)
    base_b = load(args.observations_b)
    base_policy = load(args.policy)
    base_runtime = load(args.runtime)
    baseline = evaluate_render_audit(base_a, base_b, base_policy, base_runtime)
    if baseline.get("result", {}).get("decision") != "ALLOW" or baseline.get("result", {}).get("risk") != "CLEAN":
        raise AssertionError("baseline render audit must be ALLOW/CLEAN")

    Case = tuple[str, str, Callable[[dict, dict, dict, dict], list[dict] | None]]
    cases: list[Case] = []

    def add(name: str, expected: str, mutate: Callable[[dict, dict, dict, dict], list[dict] | None]) -> None:
        cases.append((name, expected, mutate))

    add("R01-render-blank", "RENDER_BLANK", lambda a,b,p,r: a.update(initialized=False, svgCount=0))
    add("R02-required-subject-missing", "REQUIRED_SUBJECT_MISSING", lambda a,b,p,r: a["subjects"].pop("input"))
    add("R03-label-clipped", "LABEL_CLIPPED", lambda a,b,p,r: a["subjects"]["input"].update(labelBounds=[10000,10000,20,20]))
    add("R04-label-outside", "LABEL_OUTSIDE_SUBJECT", lambda a,b,p,r: a["subjects"]["input"].update(labelBounds=[a["subjects"]["input"]["bounds"][0]-20,a["subjects"]["input"]["bounds"][1],10,10], clipBounds=[-99999,-99999,199998,199998]))
    add("R05-label-occluded", "LABEL_FULLY_OCCLUDED", lambda a,b,p,r: a["subjects"]["input"].update(labelOcclusionFraction=1.0))
    add("R06-subject-occluded", "SUBJECT_FULLY_OCCLUDED", lambda a,b,p,r: a["subjects"]["input"].update(subjectOcclusionFraction=1.0))
    add("R07-edge-crosses-label", "EDGE_CROSSES_LABEL", lambda a,b,p,r: a["subjects"]["scope"].update(labelBounds=[(a["edges"]["flow"]["points"][0][0]+a["edges"]["flow"]["points"][-1][0])/2-20,a["edges"]["flow"]["points"][0][1]-10,40,20]))

    def obstacle(a,b,p,r):
        points=a["edges"]["flow"]["points"]; x=(points[0][0]+points[-1][0])/2; y=points[0][1]
        a["subjects"]["obstacle"]={"present":True,"exactness":"renderer-exact","bounds":[x-10,y-10,20,20],"labelBounds":[x-5,y-5,10,10],"clipBounds":[x-10,y-10,20,20],"labelOcclusionFraction":0.0,"subjectOcclusionFraction":0.0,"textColor":"rgb(0,0,0)","backgroundColor":"rgb(255,255,255)"}
        p["requiredSubjects"].append({"id":"obstacle","labelInsideSubject":True});p["protectedSubjects"].append("obstacle")
    add("R08-edge-crosses-subject", "EDGE_CROSSES_SUBJECT", obstacle)
    add("R09-low-contrast", "CONTRAST_BELOW_POLICY", lambda a,b,p,r: a["subjects"]["input"].update(textColor="rgb(120,120,120)",backgroundColor="rgb(130,130,130)"))
    add("R10-external-request", "RUNTIME_EXTERNAL_REQUEST", lambda a,b,p,r: a["externalRequests"].append("https://example.invalid/font.woff2"))
    add("R11-console-error", "RENDERER_CONSOLE_ERROR", lambda a,b,p,r: a["consoleErrors"].append("renderer failed"))
    add("R12-model-mutated", "MODEL_MUTATED_BY_RENDER", lambda a,b,p,r: a.update(sourceModelUnchanged=False))
    add("R13-screenshot-empty", "SCREENSHOT_EVIDENCE_EMPTY", lambda a,b,p,r: a.update(screenshot={"sha256":"sha256:"+"0"*64,"byteLength":0,"nonEmpty":False}))
    add("R14-nondeterministic", "RENDER_NONDETERMINISTIC", lambda a,b,p,r: b["screenshot"].update(sha256="sha256:"+"9"*64))
    add("R15-renderer-identity-missing", "RENDERER_IDENTITY_MISSING", lambda a,b,p,r: r["renderer"].pop("sha256"))
    add("R16-font-identity-missing", "FONT_OR_VIEWPORT_IDENTITY_MISSING", lambda a,b,p,r: r["font"].pop("sha256"))
    add("R17-unsupported-exactness", "UNSUPPORTED_RENDER_EXACTNESS", lambda a,b,p,r: a["subjects"]["input"].update(exactness="approximate"))
    add("R18-edge-route-not-exact", "EDGE_ROUTE_NOT_RENDERER_EXACT", lambda a,b,p,r: a["edges"]["flow"].update(exactness="model-exact"))
    add("R19-semantic-contaminated", "SEMANTIC_CHANNEL_CONTAMINATED", lambda a,b,p,r: a.update(semanticDigest="sha256:"+"8"*64))

    def bad_waiver(a,b,p,r):
        a["subjects"]["scope"].update(labelBounds=[(a["edges"]["flow"]["points"][0][0]+a["edges"]["flow"]["points"][-1][0])/2-20,a["edges"]["flow"]["points"][0][1]-10,40,20])
        pre=evaluate_render_audit(a,b,p,r)
        finding=next(item for item in pre["result"]["findings"] if item["code"]=="EDGE_CROSSES_LABEL")
        return [{"kind":"diagram.renderWaiver.v1","findingKey":sha256_json(finding),"factsSha256":pre["facts_sha256"],"changesObservation":True,"approvalRef":"adrs#bad"}]
    add("R20-waiver-changed-observation", "WAIVER_CHANGED_OBSERVATION", bad_waiver)
    add("R21-duplicate-render-state", "DUPLICATE_RENDER_STATE", lambda a,b,p,r: a["duplicateRenderStatePaths"].append("state/render-state.json"))

    matrix=[]
    for name,expected,mutate in cases:
        a=copy.deepcopy(base_a);b=copy.deepcopy(base_b);p=copy.deepcopy(base_policy);r=copy.deepcopy(base_runtime)
        candidate_waivers=mutate(a,b,p,r)
        if name != "R14-nondeterministic":
            b=copy.deepcopy(a)
        waivers=candidate_waivers if isinstance(candidate_waivers,list) else None
        if name == "R20-waiver-changed-observation":
            pre=evaluate_render_audit(a,b,p,r)
            finding=next(item for item in pre["result"]["findings"] if item["code"]=="EDGE_CROSSES_LABEL")
            waivers=[{"kind":"diagram.renderWaiver.v1","findingKey":sha256_json(finding),"factsSha256":pre["facts_sha256"],"changesObservation":True,"approvalRef":"adrs#bad"}]
        first=evaluate_render_audit(a,b,p,r,waivers=waivers)
        second=evaluate_render_audit(a,b,p,r,waivers=copy.deepcopy(waivers))
        passed=expected in codes(first) and receipt_bytes(first)==receipt_bytes(second)
        matrix.append({"case":name,"status":"PASS" if passed else "FAIL","expectedCode":expected,"codes":sorted(codes(first)),"deterministic":receipt_bytes(first)==receipt_bytes(second)})
    if not all(item["status"]=="PASS" for item in matrix):
        raise AssertionError(json.dumps(matrix,indent=2))
    result={
        "kind":"diagram.renderAuditProof.v1","status":"PASS","destructiveCaseCount":len(matrix),"destructiveCases":matrix,
        "baselineDecision":"ALLOW","baselineRisk":"CLEAN","baselineReceiptSha256":"sha256:"+__import__('hashlib').sha256(receipt_bytes(baseline)).hexdigest(),
        "semanticChannelUnchanged":True,"renderStatePersisted":False,"authority":False,"publicationAdmissible":False,"businessOutcomeAchieved":False,"corporateSaleOutcomeAchieved":False,
    }
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps(result,indent=2,sort_keys=True));return 0


if __name__=="__main__":
    raise SystemExit(main())
