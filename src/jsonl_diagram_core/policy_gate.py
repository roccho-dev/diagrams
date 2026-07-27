from __future__ import annotations

from datetime import datetime
from typing import Any

from .approval_receipt import validate_approval_receipt
from .io import canonical_json, sha256_text

JsonObj = dict[str, Any]
_ALLOWED_EFFECTS = {"DENY", "REVIEW", "INFO"}
_WAIVER_KEYS = {
    "schema", "waiverId", "findingKey", "subjectDigest", "findingDigest",
    "policyDigest", "reason", "evidenceRefs", "approvalReceiptRef",
    "approvalReceiptDigest", "issuedAt", "expiresAt",
}


def _digest(value: Any) -> str:
    return "sha256:" + sha256_text(canonical_json(value))


def _instant(value: str, field: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def policy_digest(policy: JsonObj) -> str:
    return _digest(policy)


def gate_findings(
    *,
    semantic_model_digest: str,
    verification: str,
    findings: list[JsonObj],
    policy: JsonObj,
    waivers: list[JsonObj],
    approval_receipts: list[JsonObj],
    repository: str,
    candidate_revision: str,
    as_of: str,
) -> tuple[JsonObj, JsonObj]:
    if policy.get("schema") != "DiagramPolicy.v1":
        raise ValueError("policy schema must be DiagramPolicy.v1")
    rules = policy.get("rules")
    if not isinstance(rules, dict):
        raise ValueError("policy rules must be an object")
    if not isinstance(repository, str) or not repository:
        raise ValueError("repository is required")
    if not isinstance(candidate_revision, str) or not candidate_revision:
        raise ValueError("candidate_revision is required")
    max_days = int(policy.get("maxWaiverDays", 31))
    evaluated_at = _instant(as_of, "as_of")
    p_digest = policy_digest(policy)

    finding_by_key: dict[str, JsonObj] = {}
    gate_errors: list[JsonObj] = []
    for finding in findings:
        key = str(finding.get("findingKey", ""))
        if not key or key in finding_by_key:
            gate_errors.append({"code": "invalid_or_duplicate_finding_key", "findingKey": key})
        else:
            finding_by_key[key] = finding

    receipt_by_ref: dict[str, JsonObj] = {}
    for receipt in approval_receipts:
        if not isinstance(receipt, dict):
            gate_errors.append({"code": "APPROVAL_RECEIPT_VALIDATION_EXCEPTION", "actual": type(receipt).__name__})
            continue
        ref = receipt.get("approval_id")
        if not isinstance(ref, str) or not ref or ref in receipt_by_ref:
            gate_errors.append({"code": "APPROVAL_RECEIPT_SCOPE_MISMATCH", "approvalReceiptRef": ref, "actual": "empty or duplicate approval_id"})
            continue
        receipt_by_ref[ref] = receipt

    waiver_by_key: dict[str, JsonObj] = {}
    for waiver in waivers:
        if not isinstance(waiver, dict):
            gate_errors.append({"code": "waiver_schema_invalid", "actual": type(waiver).__name__})
            continue
        if "approvalRef" in waiver:
            gate_errors.append({"code": "FREE_FORM_APPROVAL_REF_FORBIDDEN", "waiverId": waiver.get("waiverId")})
            continue
        unknown = sorted(set(waiver) - _WAIVER_KEYS)
        if unknown:
            gate_errors.append({"code": "waiver_unknown_fields", "fields": unknown, "waiverId": waiver.get("waiverId")})
            continue
        if waiver.get("schema") != "DiagramWaiver.v1":
            gate_errors.append({"code": "waiver_schema_invalid", "waiverId": waiver.get("waiverId")})
            continue
        key = str(waiver.get("findingKey", ""))
        if not key or key in waiver_by_key:
            gate_errors.append({"code": "waiver_duplicate_or_empty_finding_key", "findingKey": key})
            continue
        waiver_by_key[key] = waiver
        if key not in finding_by_key:
            gate_errors.append({"code": "waiver_stale_or_unknown_finding", "findingKey": key, "waiverId": waiver.get("waiverId")})

    dispositions: list[JsonObj] = []
    open_effects: list[str] = []
    accepted_count = 0
    used_receipts: set[str] = set()
    for key in sorted(finding_by_key):
        finding = finding_by_key[key]
        rule_id = str(finding.get("ruleId", ""))
        rule = rules.get(rule_id)
        if not isinstance(rule, dict):
            gate_errors.append({"code": "unknown_policy_rule", "ruleId": rule_id, "findingKey": key})
            dispositions.append({"findingKey": key, "state": "open", "effect": "DENY"})
            open_effects.append("DENY")
            continue
        effect = str(rule.get("effect", ""))
        if effect not in _ALLOWED_EFFECTS:
            gate_errors.append({"code": "invalid_policy_effect", "ruleId": rule_id, "effect": effect})
            effect = "DENY"
        if effect == "INFO":
            dispositions.append({"findingKey": key, "state": "not_required", "effect": effect})
            continue

        waiver = waiver_by_key.get(key)
        accepted = False
        if waiver is not None:
            waiver_errors: list[str] = []
            if finding.get("ruleClass") == "integrity" or not bool(rule.get("waivable", False)):
                waiver_errors.append("unwaivable")
            if waiver.get("subjectDigest") != finding.get("subjectDigest"):
                waiver_errors.append("subject_digest_mismatch")
            if waiver.get("findingDigest") != finding.get("findingDigest"):
                waiver_errors.append("finding_digest_mismatch")
            if waiver.get("policyDigest") != p_digest:
                waiver_errors.append("policy_digest_mismatch")
            try:
                issued = _instant(str(waiver.get("issuedAt", "")), "issuedAt")
                expires = _instant(str(waiver.get("expiresAt", "")), "expiresAt")
                if issued > evaluated_at:
                    waiver_errors.append("future_issued")
                if expires < evaluated_at:
                    waiver_errors.append("expired")
                if expires <= issued:
                    waiver_errors.append("invalid_interval")
                if (expires - issued).total_seconds() > max_days * 86400:
                    waiver_errors.append("over_duration")
            except Exception as exc:
                waiver_errors.append(f"invalid_time:{exc}")
            if not str(waiver.get("reason", "")).strip():
                waiver_errors.append("reason_required")
            if not isinstance(waiver.get("evidenceRefs"), list) or not waiver.get("evidenceRefs"):
                waiver_errors.append("evidence_refs_required")

            receipt_errors, receipt = validate_approval_receipt(
                receipt_ref=waiver.get("approvalReceiptRef"),
                expected_digest=waiver.get("approvalReceiptDigest"),
                receipts=receipt_by_ref,
                repository=repository,
                candidate_revision=candidate_revision,
                finding=finding,
                policy_digest=p_digest,
                as_of=as_of,
            )
            if receipt_errors:
                for error in receipt_errors:
                    gate_errors.append({
                        **error,
                        "waiverId": waiver.get("waiverId"),
                        "findingKey": key,
                    })
            if waiver_errors:
                gate_errors.append({
                    "code": "waiver_invalid",
                    "waiverId": waiver.get("waiverId"),
                    "findingKey": key,
                    "reasons": sorted(waiver_errors),
                })
            if not waiver_errors and not receipt_errors and receipt is not None:
                accepted = True
                used_receipts.add(str(waiver["approvalReceiptRef"]))

        if accepted:
            accepted_count += 1
            dispositions.append({
                "findingKey": key,
                "state": "accepted",
                "effect": effect,
                "waiverId": waiver["waiverId"],
                "expiresAt": waiver["expiresAt"],
                "decisionRefs": [waiver["approvalReceiptRef"], *waiver["evidenceRefs"]],
                "approvalReceiptDigest": waiver["approvalReceiptDigest"],
            })
        else:
            dispositions.append({"findingKey": key, "state": "open", "effect": effect})
            open_effects.append(effect)

    gate_status = "ERROR" if gate_errors else "VALID"
    if gate_errors or "DENY" in open_effects:
        decision = "DENY"
    elif "REVIEW" in open_effects:
        decision = "REVIEW"
    else:
        decision = "ALLOW"
    if open_effects:
        risk = "OPEN"
    elif accepted_count:
        risk = "ACCEPTED"
    else:
        risk = "CLEAN"

    report: JsonObj = {
        "schema": "DiagramGateReport.v1",
        "semanticModelDigest": semantic_model_digest,
        "repository": repository,
        "candidateRevision": candidate_revision,
        "policyDigest": p_digest,
        "asOf": as_of,
        "verification": verification,
        "gateStatus": gate_status,
        "decision": decision,
        "risk": risk,
        "findings": findings,
        "dispositions": dispositions,
        "gateErrors": gate_errors,
        "usedApprovalReceiptRefs": sorted(used_receipts),
    }
    report["reportDigest"] = _digest(report)
    receipt: JsonObj = {
        "schema": "DiagramGateReceipt.v1",
        "semanticModelDigest": semantic_model_digest,
        "repository": repository,
        "candidateRevision": candidate_revision,
        "policyDigest": p_digest,
        "waiversDigest": _digest(waivers),
        "approvalReceiptsDigest": _digest(approval_receipts),
        "reportDigest": report["reportDigest"],
        "asOf": as_of,
    }
    receipt["receiptId"] = _digest(receipt)
    return report, receipt
