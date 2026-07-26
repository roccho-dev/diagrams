from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from .decision_overlay import project_review_drawio as _project_review_drawio

JsonObj = dict[str, Any]


def project_review_drawio(
    drawio_text: str,
    gate_report: JsonObj,
    gate_receipt: JsonObj,
    *,
    as_of: str,
) -> tuple[str, JsonObj]:
    """Project the existing review overlay and bind accepted cells to exact receipts."""
    review_text, projection_receipt = _project_review_drawio(
        drawio_text,
        gate_report,
        gate_receipt,
        as_of=as_of,
    )
    dispositions = {
        str(row.get("findingKey")): row
        for row in gate_report.get("dispositions", [])
        if isinstance(row, dict)
    }
    root = ET.fromstring(review_text)
    for obj in root.iter():
        if obj.tag.rsplit("}", 1)[-1] != "object" or obj.get("role") != "decision-overlay":
            continue
        disposition = dispositions.get(str(obj.get("findingKey")))
        if not disposition or disposition.get("state") != "accepted":
            continue
        ref = disposition.get("decisionRefs", [None])[0]
        digest = disposition.get("approvalReceiptDigest")
        if not isinstance(ref, str) or not ref:
            raise ValueError("accepted overlay missing approval receipt reference")
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise ValueError("accepted overlay missing approval receipt digest")
        obj.set("approvalReceiptRef", ref)
        obj.set("approvalReceiptDigest", digest)
    review_text = ET.tostring(root, encoding="unicode")
    ET.fromstring(review_text)
    return review_text, projection_receipt
