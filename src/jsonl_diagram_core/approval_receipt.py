from __future__ import annotations

from datetime import datetime
from typing import Any

from .io import canonical_json, sha256_text

JsonObj = dict[str, Any]
_ALLOWED_ACTIONS = {"pull_request_review.approve", "diagram_waiver.approve"}
_RECEIPT_KEYS = {
    "kind", "approval_id", "subject", "actor", "action", "authority",
    "provider_evidence_digest", "engine_digest", "as_of", "status", "findings",
    "claim_ceiling",
}
_SUBJECT_KEYS = {"repository", "candidate_revision", "finding_digest", "policy_digest"}
_ACTION_KEYS = {"kind", "provider_review_id", "state", "submitted_at"}
_AUTHORITY_KEYS = {"grant_id", "scope_digest", "valid_from", "valid_until"}


def _digest(value: Any) -> str:
    return "sha256:" + sha256_text(canonical_json(value))


def approval_receipt_digest(receipt: JsonObj) -> str:
    return _digest(receipt)


def _instant(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _closed(value: Any, allowed: set[str], field: str) -> JsonObj:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"{field} has unknown fields: {unknown}")
    return value


def validate_approval_receipt(
    *,
    receipt_ref: Any,
    expected_digest: Any,
    receipts: dict[str, JsonObj],
    repository: str,
    candidate_revision: str,
    finding: JsonObj,
    policy_digest: str,
    as_of: str,
) -> tuple[list[JsonObj], JsonObj | None]:
    """Validate a previously produced approvalReceipt.v1 without re-evaluating authority."""
    errors: list[JsonObj] = []

    def add(code: str, expected: Any, actual: Any) -> None:
        errors.append({
            "code": code,
            "expected": expected,
            "actual": actual,
            "approvalReceiptRef": receipt_ref,
        })

    if not isinstance(receipt_ref, str) or not receipt_ref:
        add("APPROVAL_RECEIPT_MISSING", "non-empty approvalReceiptRef", receipt_ref)
        return errors, None
    receipt = receipts.get(receipt_ref)
    if receipt is None:
        add("APPROVAL_RECEIPT_MISSING", receipt_ref, None)
        return errors, None

    try:
        receipt = _closed(receipt, _RECEIPT_KEYS, "approval receipt")
    except Exception as exc:
        add("APPROVAL_RECEIPT_VALIDATION_EXCEPTION", "closed approvalReceipt.v1", str(exc))
        return errors, None

    actual_digest = approval_receipt_digest(receipt)
    if expected_digest != actual_digest:
        add("APPROVAL_RECEIPT_DIGEST_MISMATCH", actual_digest, expected_digest)
    if receipt.get("approval_id") != receipt_ref:
        add("APPROVAL_RECEIPT_SCOPE_MISMATCH", receipt_ref, receipt.get("approval_id"))
    if receipt.get("kind") != "approvalReceipt.v1":
        add("APPROVAL_RECEIPT_KIND_UNKNOWN", "approvalReceipt.v1", receipt.get("kind"))
    if receipt.get("status") != "VALID":
        add("APPROVAL_RECEIPT_NOT_VALID", "VALID", receipt.get("status"))
    if receipt.get("findings") not in ([], None):
        add("APPROVAL_RECEIPT_NOT_VALID", [], receipt.get("findings"))

    try:
        subject = _closed(receipt.get("subject"), _SUBJECT_KEYS, "receipt subject")
        action = _closed(receipt.get("action"), _ACTION_KEYS, "receipt action")
        authority = _closed(receipt.get("authority"), _AUTHORITY_KEYS, "receipt authority")
    except Exception as exc:
        add("APPROVAL_RECEIPT_VALIDATION_EXCEPTION", "closed subject/action/authority", str(exc))
        return errors, receipt

    if subject.get("repository") != repository:
        add("APPROVAL_RECEIPT_REPOSITORY_MISMATCH", repository, subject.get("repository"))
    if subject.get("candidate_revision") != candidate_revision:
        add("APPROVAL_RECEIPT_CANDIDATE_MISMATCH", candidate_revision, subject.get("candidate_revision"))
    if subject.get("finding_digest") != finding.get("findingDigest"):
        add("APPROVAL_RECEIPT_FINDING_MISMATCH", finding.get("findingDigest"), subject.get("finding_digest"))
    if subject.get("policy_digest") != policy_digest:
        add("APPROVAL_RECEIPT_POLICY_MISMATCH", policy_digest, subject.get("policy_digest"))
    if action.get("kind") not in _ALLOWED_ACTIONS:
        add("APPROVAL_RECEIPT_ACTION_NOT_ALLOWED", sorted(_ALLOWED_ACTIONS), action.get("kind"))
    if action.get("state") != "APPROVED":
        add("APPROVAL_RECEIPT_NOT_VALID", "APPROVED", action.get("state"))

    for field, code in (
        ("scope_digest", "APPROVAL_RECEIPT_SCOPE_MISMATCH"),
        ("grant_id", "APPROVAL_RECEIPT_SCOPE_MISMATCH"),
    ):
        if not isinstance(authority.get(field), str) or not authority.get(field):
            add(code, f"non-empty {field}", authority.get(field))
    for field, code in (
        ("engine_digest", "APPROVAL_RECEIPT_ENGINE_UNKNOWN"),
        ("provider_evidence_digest", "APPROVAL_RECEIPT_SCOPE_MISMATCH"),
    ):
        value = receipt.get(field)
        if not isinstance(value, str) or not value.startswith("sha256:"):
            add(code, "sha256 digest", value)

    try:
        gate_time = _instant(as_of, "as_of")
        receipt_time = _instant(receipt.get("as_of"), "receipt.as_of")
        action_time = _instant(action.get("submitted_at"), "action.submitted_at")
        valid_from = _instant(authority.get("valid_from"), "authority.valid_from")
        valid_until = _instant(authority.get("valid_until"), "authority.valid_until")
        if not (valid_from <= action_time <= valid_until):
            add("APPROVAL_RECEIPT_TIME_MISMATCH", [authority.get("valid_from"), authority.get("valid_until")], action.get("submitted_at"))
        if not (action_time <= receipt_time <= gate_time):
            add("APPROVAL_RECEIPT_TIME_MISMATCH", f"{action.get('submitted_at')} <= receipt.as_of <= {as_of}", receipt.get("as_of"))
    except Exception as exc:
        add("APPROVAL_RECEIPT_TIME_MISMATCH", "timezone-aware ordered timestamps", str(exc))

    ceiling = receipt.get("claim_ceiling")
    if not isinstance(ceiling, dict) or any(value is not False for value in ceiling.values()):
        add("APPROVAL_RECEIPT_SCOPE_MISMATCH", "all receipt claim-ceiling values false", ceiling)

    return sorted(errors, key=lambda row: (row["code"], canonical_json(row))), receipt
