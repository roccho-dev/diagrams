from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

Json = dict[str, Any]
HEX_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
TERMINAL_CODES = {
    "RENDER_BLANK",
    "REQUIRED_SUBJECT_MISSING",
    "LABEL_CLIPPED",
    "LABEL_OUTSIDE_SUBJECT",
    "LABEL_FULLY_OCCLUDED",
    "SUBJECT_FULLY_OCCLUDED",
    "EDGE_CROSSES_LABEL",
    "EDGE_CROSSES_SUBJECT",
    "CONTRAST_BELOW_POLICY",
    "RUNTIME_EXTERNAL_REQUEST",
    "RENDERER_CONSOLE_ERROR",
    "MODEL_MUTATED_BY_RENDER",
    "SCREENSHOT_EVIDENCE_EMPTY",
    "RENDER_NONDETERMINISTIC",
    "RENDERER_IDENTITY_MISSING",
    "FONT_OR_VIEWPORT_IDENTITY_MISSING",
    "UNSUPPORTED_RENDER_EXACTNESS",
    "EDGE_ROUTE_NOT_RENDERER_EXACT",
    "SEMANTIC_CHANNEL_CONTAMINATED",
    "WAIVER_CHANGED_OBSERVATION",
    "DUPLICATE_RENDER_STATE",
}


class RenderAuditInputError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def receipt_bytes(value: Json) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def _require(value: Any, code: str, message: str) -> None:
    if not value:
        raise RenderAuditInputError(code, message)


def _digest(value: Any, name: str) -> str:
    _require(isinstance(value, str) and HEX_DIGEST.fullmatch(value), "RENDERER_IDENTITY_MISSING", f"invalid {name}")
    return value


def _finite(value: Any, name: str) -> float:
    _require(isinstance(value, (int, float)) and math.isfinite(float(value)), "UNSUPPORTED_RENDER_EXACTNESS", f"invalid {name}")
    return float(value)


def _rect(value: Any, name: str) -> tuple[float, float, float, float]:
    _require(isinstance(value, list) and len(value) == 4, "UNSUPPORTED_RENDER_EXACTNESS", f"invalid {name}")
    x, y, width, height = (_finite(item, name) for item in value)
    _require(width >= 0 and height >= 0, "UNSUPPORTED_RENDER_EXACTNESS", f"negative {name}")
    return x, y, width, height


def _rect_inside(inner: tuple[float, float, float, float], outer: tuple[float, float, float, float], tolerance: float) -> bool:
    ix, iy, iw, ih = inner
    ox, oy, ow, oh = outer
    return (
        ix >= ox - tolerance
        and iy >= oy - tolerance
        and ix + iw <= ox + ow + tolerance
        and iy + ih <= oy + oh + tolerance
    )


def _rect_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float], *, strict: bool = True) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if strict:
        return max(ax, bx) < min(ax + aw, bx + bw) and max(ay, by) < min(ay + ah, by + bh)
    return max(ax, bx) <= min(ax + aw, bx + bw) and max(ay, by) <= min(ay + ah, by + bh)


def _segment_intersects_rect(a: list[float], b: list[float], rect: tuple[float, float, float, float], clearance: float) -> bool:
    x1, y1 = _finite(a[0], "edge point"), _finite(a[1], "edge point")
    x2, y2 = _finite(b[0], "edge point"), _finite(b[1], "edge point")
    rx, ry, rw, rh = rect
    rx -= clearance
    ry -= clearance
    rw += 2 * clearance
    rh += 2 * clearance
    if max(x1, x2) < rx or min(x1, x2) > rx + rw or max(y1, y2) < ry or min(y1, y2) > ry + rh:
        return False
    if x1 == x2:
        return rx <= x1 <= rx + rw and not (max(y1, y2) < ry or min(y1, y2) > ry + rh)
    if y1 == y2:
        return ry <= y1 <= ry + rh and not (max(x1, x2) < rx or min(x1, x2) > rx + rw)

    # Liang-Barsky clipping for a general rendered polyline segment.
    dx, dy = x2 - x1, y2 - y1
    p = (-dx, dx, -dy, dy)
    q = (x1 - rx, rx + rw - x1, y1 - ry, ry + rh - y1)
    low, high = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return False
            continue
        ratio = qi / pi
        if pi < 0:
            low = max(low, ratio)
        else:
            high = min(high, ratio)
        if low > high:
            return False
    return True


def _parse_rgb(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text.startswith("#") and len(text) in {4, 7}:
        if len(text) == 4:
            text = "#" + "".join(ch * 2 for ch in text[1:])
        try:
            return tuple(int(text[index:index + 2], 16) / 255.0 for index in (1, 3, 5))  # type: ignore[return-value]
        except ValueError:
            return None
    match = re.fullmatch(r"rgba?\(([^)]+)\)", text)
    if match:
        parts = [part.strip() for part in match.group(1).split(",")]
        if len(parts) >= 3:
            try:
                return tuple(float(parts[index]) / 255.0 for index in range(3))  # type: ignore[return-value]
            except ValueError:
                return None
    return None


def _luminance(rgb: tuple[float, float, float]) -> float:
    values = []
    for component in rgb:
        values.append(component / 12.92 if component <= 0.04045 else ((component + 0.055) / 1.055) ** 2.4)
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def _contrast(foreground: Any, background: Any) -> float | None:
    fg, bg = _parse_rgb(foreground), _parse_rgb(background)
    if fg is None or bg is None:
        return None
    a, b = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


@dataclass(frozen=True)
class Finding:
    code: str
    subjects: tuple[str, ...]
    evidence: Json
    exactness: str = "renderer-exact"

    def as_json(self) -> Json:
        return {
            "kind": "diagram.renderFinding.v1",
            "code": self.code,
            "subject_ids": list(self.subjects),
            "exactness": self.exactness,
            "evidence": self.evidence,
        }


def _finding(code: str, subjects: Iterable[str], **evidence: Any) -> Finding:
    _require(code in TERMINAL_CODES, "UNSUPPORTED_RENDER_EXACTNESS", f"unknown finding code {code}")
    return Finding(code=code, subjects=tuple(sorted(str(subject) for subject in subjects)), evidence=evidence)


def _runtime_complete(runtime: Any) -> bool:
    if not isinstance(runtime, dict):
        return False
    renderer = runtime.get("renderer")
    container = runtime.get("container")
    browser = runtime.get("browser")
    font = runtime.get("font")
    viewport = runtime.get("viewport")
    return bool(
        isinstance(renderer, dict)
        and renderer.get("product") == "draw.io GraphViewer"
        and renderer.get("version")
        and HEX_DIGEST.fullmatch(str(renderer.get("sha256", "")))
        and isinstance(container, dict)
        and container.get("digest")
        and HEX_DIGEST.fullmatch(str(container.get("osReleaseSha256", "")))
        and isinstance(browser, dict)
        and browser.get("version")
        and HEX_DIGEST.fullmatch(str(browser.get("executableSha256", "")))
        and isinstance(font, dict)
        and font.get("family")
        and HEX_DIGEST.fullmatch(str(font.get("sha256", "")))
        and isinstance(viewport, dict)
        and int(viewport.get("width", 0)) > 0
        and int(viewport.get("height", 0)) > 0
        and float(viewport.get("devicePixelRatio", 0)) > 0
        and runtime.get("theme") in {"light", "dark"}
    )


def _normalized_facts(observation: Json) -> Json:
    return {
        "initialized": observation.get("initialized"),
        "sourceModelUnchanged": observation.get("sourceModelUnchanged"),
        "semanticStatus": observation.get("semanticStatus"),
        "semanticDigest": observation.get("semanticDigest"),
        "pageIds": observation.get("pageIds"),
        "subjects": observation.get("subjects"),
        "edges": observation.get("edges"),
        "svgCount": observation.get("svgCount"),
        "externalRequests": observation.get("externalRequests"),
        "consoleErrors": observation.get("consoleErrors"),
        "pageErrors": observation.get("pageErrors"),
        "unsupported": observation.get("unsupported"),
        "duplicateRenderStatePaths": observation.get("duplicateRenderStatePaths"),
        "screenshot": observation.get("screenshot"),
    }


def evaluate_render_audit(
    observation_a: Json,
    observation_b: Json,
    policy: Json,
    runtime: Json,
    *,
    waivers: list[Json] | None = None,
) -> Json:
    """Evaluate two clean fixed-runtime observations into one deterministic receipt.

    Observations are non-authority runtime facts. The function never rewrites source or
    semantic status. Valid waivers can only mark exact findings as accepted.
    """

    try:
        _require(policy.get("kind") == "diagram.renderAuditPolicy.v1", "UNSUPPORTED_RENDER_EXACTNESS", "policy kind")
        source = policy.get("source")
        _require(isinstance(source, dict), "RENDERER_IDENTITY_MISSING", "source identity missing")
        source_digest = _digest(source.get("mxfileSha256"), "source mxfile digest")
        semantic_digest = _digest(source.get("semanticDigest"), "semantic digest")
        page_ids = source.get("pageIds")
        _require(isinstance(page_ids, list) and all(isinstance(item, str) for item in page_ids), "RENDERER_IDENTITY_MISSING", "page identities")
        _require(isinstance(runtime, dict), "RENDERER_IDENTITY_MISSING", "runtime identity missing")
        renderer = runtime.get("renderer")
        container = runtime.get("container")
        browser = runtime.get("browser")
        _require(
            isinstance(renderer, dict)
            and renderer.get("product") == "draw.io GraphViewer"
            and renderer.get("version")
            and HEX_DIGEST.fullmatch(str(renderer.get("sha256", "")))
            and isinstance(container, dict)
            and container.get("digest")
            and HEX_DIGEST.fullmatch(str(container.get("osReleaseSha256", "")))
            and isinstance(browser, dict)
            and browser.get("version")
            and HEX_DIGEST.fullmatch(str(browser.get("executableSha256", ""))),
            "RENDERER_IDENTITY_MISSING",
            "renderer/container/browser identity incomplete",
        )
        font = runtime.get("font")
        viewport = runtime.get("viewport")
        _require(
            isinstance(font, dict)
            and font.get("family")
            and HEX_DIGEST.fullmatch(str(font.get("sha256", "")))
            and isinstance(viewport, dict)
            and int(viewport.get("width", 0)) > 0
            and int(viewport.get("height", 0)) > 0
            and float(viewport.get("devicePixelRatio", 0)) > 0
            and runtime.get("theme") in {"light", "dark"},
            "FONT_OR_VIEWPORT_IDENTITY_MISSING",
            "font/viewport/theme identity incomplete",
        )
        _require(policy.get("asOf"), "RENDERER_IDENTITY_MISSING", "as_of missing")

        findings: list[Finding] = []
        errors: list[Json] = []
        coverage: list[Json] = []

        for observation_name, observation in (("a", observation_a), ("b", observation_b)):
            if observation.get("sourceMxfileSha256") != source_digest:
                findings.append(_finding("MODEL_MUTATED_BY_RENDER", ["source"], observation=observation_name, expected=source_digest, actual=observation.get("sourceMxfileSha256")))
            if observation.get("semanticDigest") != semantic_digest or observation.get("semanticStatus") != "PASS":
                findings.append(_finding("SEMANTIC_CHANNEL_CONTAMINATED", ["semantic"], observation=observation_name, expectedDigest=semantic_digest, actualDigest=observation.get("semanticDigest"), semanticStatus=observation.get("semanticStatus")))
            if sorted(observation.get("pageIds") or []) != sorted(page_ids):
                findings.append(_finding("RENDER_BLANK", ["pages"], observation=observation_name, expected=page_ids, actual=observation.get("pageIds")))
            if not observation.get("initialized") or int(observation.get("svgCount", 0)) < 1:
                findings.append(_finding("RENDER_BLANK", ["document"], observation=observation_name, initialized=observation.get("initialized"), svgCount=observation.get("svgCount")))
            if not observation.get("sourceModelUnchanged"):
                findings.append(_finding("MODEL_MUTATED_BY_RENDER", ["source"], observation=observation_name))
            for request in observation.get("externalRequests") or []:
                findings.append(_finding("RUNTIME_EXTERNAL_REQUEST", ["runtime"], observation=observation_name, request=request))
            for message in [*(observation.get("consoleErrors") or []), *(observation.get("pageErrors") or [])]:
                findings.append(_finding("RENDERER_CONSOLE_ERROR", ["runtime"], observation=observation_name, message=message))
            for item in observation.get("unsupported") or []:
                coverage.append({"observation": observation_name, **item})
            if observation.get("duplicateRenderStatePaths"):
                findings.append(_finding("DUPLICATE_RENDER_STATE", ["repository"], observation=observation_name, paths=observation.get("duplicateRenderStatePaths")))
            screenshot = observation.get("screenshot")
            if not isinstance(screenshot, dict) or not screenshot.get("nonEmpty") or int(screenshot.get("byteLength", 0)) <= 0 or not HEX_DIGEST.fullmatch(str(screenshot.get("sha256", ""))):
                findings.append(_finding("SCREENSHOT_EVIDENCE_EMPTY", ["screenshot"], observation=observation_name, screenshot=screenshot))

        if sha256_json(_normalized_facts(observation_a)) != sha256_json(_normalized_facts(observation_b)):
            findings.append(_finding("RENDER_NONDETERMINISTIC", ["render"], a=sha256_json(_normalized_facts(observation_a)), b=sha256_json(_normalized_facts(observation_b))))

        required_subjects = policy.get("requiredSubjects")
        _require(isinstance(required_subjects, list), "UNSUPPORTED_RENDER_EXACTNESS", "required subjects")
        subjects = observation_a.get("subjects") if isinstance(observation_a.get("subjects"), dict) else {}
        label_tolerance = float(policy.get("labelTolerance", 0.5))
        min_contrast = float(policy.get("minContrastRatio", 4.5))
        fully_occluded_at = float(policy.get("fullyOccludedAt", 0.99))

        for required in required_subjects:
            _require(isinstance(required, dict) and required.get("id"), "UNSUPPORTED_RENDER_EXACTNESS", "subject policy")
            subject_id = str(required["id"])
            subject = subjects.get(subject_id)
            if not isinstance(subject, dict) or not subject.get("present"):
                findings.append(_finding("REQUIRED_SUBJECT_MISSING", [subject_id]))
                continue
            exactness = subject.get("exactness")
            if exactness not in {"renderer-exact", "model-exact"}:
                findings.append(_finding("UNSUPPORTED_RENDER_EXACTNESS", [subject_id], exactness=exactness))
            subject_bounds = _rect(subject.get("bounds"), f"{subject_id} bounds")
            label_bounds = _rect(subject.get("labelBounds"), f"{subject_id} label bounds")
            clip_bounds = _rect(subject.get("clipBounds", subject.get("bounds")), f"{subject_id} clip bounds")
            if not _rect_inside(label_bounds, clip_bounds, label_tolerance):
                findings.append(_finding("LABEL_CLIPPED", [subject_id], labelBounds=label_bounds, clipBounds=clip_bounds, tolerance=label_tolerance))
            if required.get("labelInsideSubject", True) and not _rect_inside(label_bounds, subject_bounds, label_tolerance):
                findings.append(_finding("LABEL_OUTSIDE_SUBJECT", [subject_id], labelBounds=label_bounds, subjectBounds=subject_bounds, tolerance=label_tolerance))
            if float(subject.get("labelOcclusionFraction", 0.0)) >= fully_occluded_at:
                findings.append(_finding("LABEL_FULLY_OCCLUDED", [subject_id], fraction=subject.get("labelOcclusionFraction")))
            if float(subject.get("subjectOcclusionFraction", 0.0)) >= fully_occluded_at:
                findings.append(_finding("SUBJECT_FULLY_OCCLUDED", [subject_id], fraction=subject.get("subjectOcclusionFraction")))
            ratio = _contrast(subject.get("textColor"), subject.get("backgroundColor"))
            if ratio is None:
                coverage.append({"subject": subject_id, "rule": "contrast", "exactness": "unsupported"})
            elif ratio < min_contrast:
                findings.append(_finding("CONTRAST_BELOW_POLICY", [subject_id], ratio=round(ratio, 6), minimum=min_contrast, foreground=subject.get("textColor"), background=subject.get("backgroundColor")))

        edges = observation_a.get("edges") if isinstance(observation_a.get("edges"), dict) else {}
        protected_labels = set(str(item) for item in policy.get("protectedLabels") or [])
        protected_subjects = set(str(item) for item in policy.get("protectedSubjects") or [])
        edge_clearance = float(policy.get("edgeClearance", 0.0))
        for edge_policy in policy.get("requiredEdges") or []:
            _require(isinstance(edge_policy, dict) and edge_policy.get("id"), "UNSUPPORTED_RENDER_EXACTNESS", "edge policy")
            edge_id = str(edge_policy["id"])
            edge = edges.get(edge_id)
            if not isinstance(edge, dict) or not edge.get("present"):
                findings.append(_finding("REQUIRED_SUBJECT_MISSING", [edge_id]))
                continue
            points = edge.get("points")
            if edge.get("exactness") != "renderer-exact" or not isinstance(points, list) or len(points) < 2:
                findings.append(_finding("EDGE_ROUTE_NOT_RENDERER_EXACT", [edge_id], exactness=edge.get("exactness")))
                continue
            source_id, target_id = str(edge.get("source")), str(edge.get("target"))
            related_subjects = {source_id, target_id, *(str(item) for item in edge_policy.get("relatedSubjects", []))}
            for subject_id in protected_labels:
                subject = subjects.get(subject_id)
                if isinstance(subject, dict) and subject.get("present"):
                    label_bounds = _rect(subject.get("labelBounds"), f"{subject_id} label bounds")
                    if any(_segment_intersects_rect(a, b, label_bounds, edge_clearance) for a, b in zip(points, points[1:])):
                        findings.append(_finding("EDGE_CROSSES_LABEL", [edge_id, subject_id], edge=edge_id, label=subject_id, points=points, labelBounds=label_bounds))
            for subject_id in protected_subjects - related_subjects:
                subject = subjects.get(subject_id)
                if isinstance(subject, dict) and subject.get("present"):
                    subject_bounds = _rect(subject.get("bounds"), f"{subject_id} bounds")
                    if any(_segment_intersects_rect(a, b, subject_bounds, edge_clearance) for a, b in zip(points, points[1:])):
                        findings.append(_finding("EDGE_CROSSES_SUBJECT", [edge_id, subject_id], edge=edge_id, subject=subject_id, points=points, subjectBounds=subject_bounds))

        if coverage and policy.get("unsupportedExactness") == "ERROR":
            findings.append(_finding("UNSUPPORTED_RENDER_EXACTNESS", [str(item.get("subject", item.get("rule", "coverage"))) for item in coverage], coverage=coverage))

        # Stable deduplication keeps the smallest exact finding set deterministic.
        deduplicated: dict[str, Json] = {}
        for finding in findings:
            payload = finding.as_json()
            key = sha256_json(payload)
            deduplicated[key] = payload
        findings_json = [deduplicated[key] for key in sorted(deduplicated)]
        facts = {
            "kind": "diagram.renderFacts.v1",
            "source": {"mxfileSha256": source_digest, "semanticDigest": semantic_digest, "pageIds": sorted(page_ids)},
            "runtime": runtime,
            "observations": [_normalized_facts(observation_a), _normalized_facts(observation_b)],
            "coverage": sorted(coverage, key=canonical_json),
        }
        facts_digest = sha256_json(facts)

        dispositions: list[Json] = []
        accepted_keys: set[str] = set()
        for waiver in waivers or []:
            if not isinstance(waiver, dict) or waiver.get("kind") != "diagram.renderWaiver.v1":
                findings_json.append(_finding("WAIVER_CHANGED_OBSERVATION", ["waiver"], reason="invalid waiver shape").as_json())
                continue
            if waiver.get("factsSha256") != facts_digest or waiver.get("changesObservation") or waiver.get("removesFinding"):
                findings_json.append(_finding("WAIVER_CHANGED_OBSERVATION", [str(waiver.get("findingKey", "waiver"))], waiver=waiver).as_json())
                continue
            finding_key = waiver.get("findingKey")
            matches = [item for item in findings_json if sha256_json(item) == finding_key]
            if len(matches) != 1:
                findings_json.append(_finding("WAIVER_CHANGED_OBSERVATION", [str(finding_key)], reason="finding key mismatch").as_json())
                continue
            accepted_keys.add(str(finding_key))
            dispositions.append({"kind": "diagram.renderDisposition.v1", "findingKey": finding_key, "state": "accepted", "approvalRef": waiver.get("approvalRef"), "expires": waiver.get("expires")})

        findings_json = sorted({sha256_json(item): item for item in findings_json}.values(), key=canonical_json)
        integrity_codes = {
            "RENDERER_IDENTITY_MISSING",
            "FONT_OR_VIEWPORT_IDENTITY_MISSING",
            "MODEL_MUTATED_BY_RENDER",
            "SEMANTIC_CHANNEL_CONTAMINATED",
            "WAIVER_CHANGED_OBSERVATION",
            "DUPLICATE_RENDER_STATE",
            "RENDER_NONDETERMINISTIC",
        }
        finding_keys = {sha256_json(item) for item in findings_json}
        open_keys = finding_keys - accepted_keys
        verification = "ERROR" if any(item["code"] in integrity_codes for item in findings_json) else "PARTIAL" if coverage else "COMPLETE"
        gate_status = "ERROR" if verification == "ERROR" else "VALID"
        if open_keys:
            decision, risk = "DENY", "OPEN"
        elif findings_json:
            decision, risk = "ALLOW", "ACCEPTED"
        else:
            decision, risk = "ALLOW", "CLEAN"

        screenshots = [observation_a.get("screenshot"), observation_b.get("screenshot")]
        receipt: Json = {
            "kind": "diagram.renderAudit.v1",
            "channel": "render",
            "authority": False,
            "source": {
                "adrs_merge_commit": source.get("adrsMergeCommit"),
                "decision_id": source.get("decisionId"),
                "release_id": source.get("releaseId"),
                "mxfile_sha256": source_digest,
                "semantic_digest": semantic_digest,
                "page_ids": sorted(page_ids),
            },
            "runtime": runtime,
            "engine": {"checker_version": "1.0.0", "policy_digest": sha256_json(policy)},
            "facts_sha256": facts_digest,
            "result": {
                "verification": verification,
                "gateStatus": gate_status,
                "decision": decision,
                "risk": risk,
                "findings": findings_json,
                "dispositions": sorted(dispositions, key=canonical_json),
                "errors": errors,
            },
            "screenshots": screenshots,
            "source_model_unchanged": bool(observation_a.get("sourceModelUnchanged") and observation_b.get("sourceModelUnchanged")),
            "semantic_channel_unchanged": observation_a.get("semanticDigest") == semantic_digest and observation_b.get("semanticDigest") == semantic_digest and observation_a.get("semanticStatus") == observation_b.get("semanticStatus") == "PASS",
            "renderQualityAuditComplete": verification == "COMPLETE" and gate_status == "VALID" and decision == "ALLOW",
            "publicationAdmissible": False,
            "businessOutcomeAchieved": False,
            "corporateSaleOutcomeAchieved": False,
        }
        return receipt
    except RenderAuditInputError as exc:
        return {
            "kind": "diagram.renderAudit.v1",
            "channel": "render",
            "authority": False,
            "result": {
                "verification": "ERROR",
                "gateStatus": "ERROR",
                "decision": "DENY",
                "risk": "OPEN",
                "findings": [_finding(exc.code if exc.code in TERMINAL_CODES else "UNSUPPORTED_RENDER_EXACTNESS", ["input"], message=str(exc)).as_json()],
                "dispositions": [],
                "errors": [{"code": exc.code, "message": str(exc)}],
            },
            "renderQualityAuditComplete": False,
            "publicationAdmissible": False,
            "businessOutcomeAchieved": False,
            "corporateSaleOutcomeAchieved": False,
        }
