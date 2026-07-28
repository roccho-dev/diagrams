from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

Json = dict[str, Any]
SEMANTIC_TYPES = {"diagram", "group", "node", "edge", "overlay"}
SUPPORTED_SPATIAL = {"contains", "inside", "overlaps", "touches", "disjoint"}


class ConformanceInputError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _float(value: str | None, default: float = 0.0) -> float:
    try:
        number = float(value) if value is not None else default
    except ValueError as exc:
        raise ConformanceInputError("UNSUPPORTED_GEOMETRY", f"non-numeric geometry: {value}") from exc
    if not math.isfinite(number):
        raise ConformanceInputError("UNSUPPORTED_GEOMETRY", f"non-finite geometry: {value}")
    return number


def _decode_model(diagram: ET.Element) -> ET.Element:
    children = list(diagram)
    if children:
        model = children[0]
        if _local(model.tag) != "mxGraphModel":
            raise ConformanceInputError("UNKNOWN_SCHEMA", f"unexpected page child: {model.tag}")
        return model
    payload = (diagram.text or "").strip()
    if not payload:
        raise ConformanceInputError("MALFORMED_INPUT", "diagram page has no model")
    try:
        encoded = zlib.decompress(base64.b64decode(payload, validate=True), wbits=-15).decode("utf-8")
        model = ET.fromstring(urllib.parse.unquote(encoded))
    except (ValueError, UnicodeDecodeError, zlib.error, ET.ParseError) as exc:
        raise ConformanceInputError("MALFORMED_INPUT", "invalid compressed diagram") from exc
    if _local(model.tag) != "mxGraphModel":
        raise ConformanceInputError("UNKNOWN_SCHEMA", "decoded page is not mxGraphModel")
    return model


@dataclass(frozen=True)
class ParsedPage:
    page_id: str
    page_name: str
    subjects: dict[str, Json]
    visual: dict[str, Json]


def _page_subjects(page_id: str, diagram: ET.Element, model: ET.Element) -> ParsedPage:
    root = next((item for item in model if _local(item.tag) == "root"), None)
    if root is None:
        raise ConformanceInputError("MALFORMED_INPUT", f"page {page_id} has no root")

    cells: dict[str, ET.Element] = {}
    attrs_by_cell: dict[str, Json] = {}
    for item in root:
        if _local(item.tag) in {"object", "UserObject"}:
            cell = next((child for child in item if _local(child.tag) == "mxCell"), None)
            if cell is None:
                continue
            cid = cell.get("id") or item.get("id")
            if not cid:
                raise ConformanceInputError("DUPLICATE_IDENTITY", "semantic object has no mxCell id")
            attrs = dict(cell.attrib)
            attrs.update(item.attrib)
            if item.get("label") is not None:
                attrs["value"] = item.get("label")
            cells[cid] = cell
            attrs_by_cell[cid] = attrs
        elif _local(item.tag) == "mxCell":
            cid = item.get("id")
            if not cid:
                continue
            cells[cid] = item
            attrs_by_cell[cid] = dict(item.attrib)

    absolute_cache: dict[str, tuple[float, float, float, float]] = {}

    def absolute(cid: str, stack: tuple[str, ...] = ()) -> tuple[float, float, float, float]:
        if cid in absolute_cache:
            return absolute_cache[cid]
        if cid in stack:
            raise ConformanceInputError("DUPLICATE_IDENTITY", f"parent cycle: {cid}")
        cell = cells.get(cid)
        if cell is None:
            raise ConformanceInputError("MALFORMED_INPUT", f"missing cell: {cid}")
        geometry = next((child for child in cell if _local(child.tag) == "mxGeometry"), None)
        x = _float(geometry.get("x") if geometry is not None else None)
        y = _float(geometry.get("y") if geometry is not None else None)
        w = _float(geometry.get("width") if geometry is not None else None)
        h = _float(geometry.get("height") if geometry is not None else None)
        parent = cell.get("parent")
        if parent and parent not in {"0", "1"}:
            px, py, _, _ = absolute(parent, (*stack, cid))
            x, y = x + px, y + py
        absolute_cache[cid] = (x, y, w, h)
        return absolute_cache[cid]

    cell_to_semantic: dict[str, str] = {}
    for cid, attrs in attrs_by_cell.items():
        semantic_id = attrs.get("jsonlId") or attrs.get("semanticId")
        typ = attrs.get("jsonlType") or attrs.get("semanticType")
        if semantic_id and typ in SEMANTIC_TYPES:
            if semantic_id in cell_to_semantic.values():
                raise ConformanceInputError("DUPLICATE_IDENTITY", f"duplicate subject id on page {page_id}: {semantic_id}")
            cell_to_semantic[cid] = str(semantic_id)

    subjects: dict[str, Json] = {}
    visual: dict[str, Json] = {}
    for cid, sid in cell_to_semantic.items():
        cell = cells[cid]
        attrs = attrs_by_cell[cid]
        typ = str(attrs.get("jsonlType") or attrs.get("semanticType"))
        try:
            meta = json.loads(str(attrs.get("metaJson", "{}")))
        except json.JSONDecodeError as exc:
            raise ConformanceInputError("MALFORMED_INPUT", f"invalid metaJson for {sid}") from exc
        if not isinstance(meta, dict):
            raise ConformanceInputError("MALFORMED_INPUT", f"metaJson must be object for {sid}")
        semantic_parent = attrs.get("semanticGroup") or attrs.get("semanticLane")
        if semantic_parent is None:
            semantic_parent = cell_to_semantic.get(cell.get("parent", ""))
        subject: Json = {
            "id": sid,
            "type": typ,
            "kind": str(attrs.get("semanticKind", typ)),
            "label": str(attrs.get("value", "")),
            "parent": semantic_parent,
            "meta": meta,
        }
        if typ == "edge":
            subject.update({
                "source": attrs.get("semanticSource") or cell_to_semantic.get(cell.get("source", "")),
                "target": attrs.get("semanticTarget") or cell_to_semantic.get(cell.get("target", "")),
                "state": attrs.get("semanticState") or meta.get("state"),
            })
            if not subject["source"] or not subject["target"]:
                raise ConformanceInputError("MISSING_PROVENANCE", f"edge endpoints missing for {sid}")
        if typ == "overlay":
            subject.update({
                "subject": attrs.get("semanticSubject") or meta.get("subject"),
                "state": attrs.get("semanticState") or meta.get("state"),
                "expiry": attrs.get("semanticExpiry") or meta.get("expiry"),
                "decisionRef": attrs.get("decisionRef") or meta.get("decisionRef"),
            })
        subjects[sid] = subject
        x, y, w, h = absolute(cid)
        visual[sid] = {
            "bounds": [x, y, w, h],
            "style": cell.get("style", ""),
            "z": list(root).index(next(item for item in root if item is cell or (list(item) and list(item)[0] is cell))),
        }

    return ParsedPage(page_id=page_id, page_name=diagram.get("name", ""), subjects=subjects, visual=visual)


def parse_mxfile(xml_bytes: bytes) -> dict[str, ParsedPage]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ConformanceInputError("MALFORMED_INPUT", "invalid XML") from exc
    if _local(root.tag) != "mxfile":
        raise ConformanceInputError("UNKNOWN_SCHEMA", "root must be mxfile")
    pages: dict[str, ParsedPage] = {}
    global_subjects: set[str] = set()
    for diagram in root:
        if _local(diagram.tag) != "diagram":
            continue
        page_id = diagram.get("id")
        if not page_id:
            raise ConformanceInputError("DUPLICATE_PAGE_ID", "page id required")
        if page_id in pages:
            raise ConformanceInputError("DUPLICATE_PAGE_ID", f"duplicate page id: {page_id}")
        page = _page_subjects(page_id, diagram, _decode_model(diagram))
        for subject_id in page.subjects:
            key = f"{page_id}:{subject_id}"
            if key in global_subjects:
                raise ConformanceInputError("DUPLICATE_IDENTITY", f"duplicate subject: {key}")
            global_subjects.add(key)
        pages[page_id] = page
    if not pages:
        raise ConformanceInputError("MALFORMED_INPUT", "mxfile has no pages")
    return pages


def _rect_relation(a: list[float], b: list[float]) -> Json:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw < 0 or ah < 0 or bw < 0 or bh < 0:
        raise ConformanceInputError("UNSUPPORTED_GEOMETRY", "negative rectangle dimension")
    aix1, aiy1, aix2, aiy2 = ax, ay, ax + aw, ay + ah
    bix1, biy1, bix2, biy2 = bx, by, bx + bw, by + bh
    ix = max(0.0, min(aix2, bix2) - max(aix1, bix1))
    iy = max(0.0, min(aiy2, biy2) - max(aiy1, biy1))
    intersection = ix * iy
    area_a, area_b = aw * ah, bw * bh
    contains = bix1 >= aix1 and biy1 >= aiy1 and bix2 <= aix2 and biy2 <= aiy2
    inside = aix1 >= bix1 and aiy1 >= biy1 and aix2 <= bix2 and aiy2 <= biy2
    touches = intersection == 0 and not (aix2 < bix1 or bix2 < aix1 or aiy2 < biy1 or biy2 < aiy1)
    overlaps = intersection > 0 and not contains and not inside
    disjoint = intersection == 0 and not touches
    return {
        "contains": contains,
        "inside": inside,
        "overlaps": overlaps,
        "touches": touches,
        "disjoint": disjoint,
        "aInB": 0.0 if area_a == 0 else intersection / area_a,
        "bInA": 0.0 if area_b == 0 else intersection / area_b,
    }


def semantic_selection(pages: dict[str, ParsedPage], policy: Json) -> Json:
    expected_page_ids = policy.get("pageIds")
    if expected_page_ids is not None and sorted(pages) != sorted(expected_page_ids):
        # Page set is compared later; selection still reflects actual pages.
        pass
    selected_pages: list[Json] = []
    spatial_rules = policy.get("spatialRules", [])
    if not isinstance(spatial_rules, list):
        raise ConformanceInputError("UNKNOWN_POLICY", "spatialRules must be a list")
    spatial_by_page: dict[str, list[Json]] = {}
    for rule in spatial_rules:
        if not isinstance(rule, dict):
            raise ConformanceInputError("UNKNOWN_POLICY", "spatial rule must be object")
        relation = rule.get("relation")
        if relation not in SUPPORTED_SPATIAL:
            raise ConformanceInputError("UNSUPPORTED_GEOMETRY", f"unsupported spatial relation: {relation}")
        page_id, a_id, b_id = rule.get("pageId"), rule.get("a"), rule.get("b")
        page = pages.get(str(page_id))
        if page is None or a_id not in page.visual or b_id not in page.visual:
            raise ConformanceInputError("MISSING_PROVENANCE", f"spatial subjects missing: {page_id}:{a_id}:{b_id}")
        for subject_id in (a_id, b_id):
            style = page.visual[subject_id]["style"]
            if "rotation=" in style or "shape=mxgraph" in style:
                raise ConformanceInputError("UNSUPPORTED_GEOMETRY", f"unsupported exact geometry: {subject_id}")
        observed = _rect_relation(page.visual[a_id]["bounds"], page.visual[b_id]["bounds"])
        spatial_by_page.setdefault(str(page_id), []).append({
            "a": a_id,
            "b": b_id,
            "relation": relation,
            "value": bool(observed[relation]),
            "aInB": round(float(observed["aInB"]), 12),
            "bInA": round(float(observed["bInA"]), 12),
            "tolerance": float(rule.get("tolerance", 0.0)),
        })
    for page_id in sorted(pages):
        page = pages[page_id]
        identities = []
        tree = []
        graph = []
        overlays = []
        for subject in sorted(page.subjects.values(), key=lambda item: (item["type"], item["id"])):
            typ = subject["type"]
            if typ in {"diagram", "group", "node"}:
                identities.append({key: subject.get(key) for key in ("id", "type", "kind", "label")})
                if subject.get("parent"):
                    tree.append({"child": subject["id"], "parent": subject["parent"]})
            elif typ == "edge":
                graph.append({key: subject.get(key) for key in ("id", "source", "kind", "target", "state")})
            elif typ == "overlay":
                overlays.append({key: subject.get(key) for key in ("id", "subject", "state", "expiry", "decisionRef")})
        selected_pages.append({
            "id": page_id,
            "identities": identities,
            "tree": sorted(tree, key=canonical_json),
            "graph": sorted(graph, key=canonical_json),
            "overlays": sorted(overlays, key=canonical_json),
            "spatial": sorted(spatial_by_page.get(page_id, []), key=canonical_json),
        })
    return {"pages": selected_pages}


def visual_selection(pages: dict[str, ParsedPage]) -> Json:
    return {
        "pages": [
            {"id": page_id, "subjects": [{"id": sid, **page.visual[sid]} for sid in sorted(page.visual)]}
            for page_id, page in sorted(pages.items())
        ]
    }


def _index(items: Iterable[Json], key_fields: tuple[str, ...]) -> dict[tuple[Any, ...], Json]:
    return {tuple(item.get(key) for key in key_fields): item for item in items}


def _diff_page(expected: Json, observed: Json) -> tuple[list[Json], list[Json], list[Json]]:
    missing: list[Json] = []
    additional: list[Json] = []
    changed: list[Json] = []
    specs = (
        ("identities", ("id",), "identity_changed"),
        ("tree", ("child",), "tree_changed"),
        ("graph", ("id",), "graph_changed"),
        ("overlays", ("id",), "overlay_changed"),
        ("spatial", ("a", "b", "relation"), "spatial_relation_changed"),
    )
    page_id = expected["id"]
    for channel, key_fields, change_code in specs:
        exp = _index(expected[channel], key_fields)
        obs = _index(observed[channel], key_fields)
        for key in sorted(exp.keys() - obs.keys(), key=str):
            missing.append({"kind": "diagram.semanticDiff.v1", "code": "missing_expected", "channel": channel, "page_id": page_id, "subject_ids": list(key), "expected": exp[key], "observed": None})
        for key in sorted(obs.keys() - exp.keys(), key=str):
            additional.append({"kind": "diagram.semanticDiff.v1", "code": "unapproved_observed", "channel": channel, "page_id": page_id, "subject_ids": list(key), "expected": None, "observed": obs[key]})
        for key in sorted(exp.keys() & obs.keys(), key=str):
            if channel == "spatial":
                e, o = exp[key], obs[key]
                tolerance = max(float(e.get("tolerance", 0.0)), float(o.get("tolerance", 0.0)))
                relation_changed = e.get("value") != o.get("value")
                ratio_changed = abs(float(e.get("aInB", 0.0)) - float(o.get("aInB", 0.0))) > tolerance or abs(float(e.get("bInA", 0.0)) - float(o.get("bInA", 0.0))) > tolerance
                if relation_changed or ratio_changed:
                    code = change_code if relation_changed else "overlap_ratio_changed"
                    changed.append({"kind": "diagram.semanticDiff.v1", "code": code, "channel": channel, "page_id": page_id, "subject_ids": list(key[:2]), "expected": e, "observed": o})
            elif exp[key] != obs[key]:
                changed.append({"kind": "diagram.semanticDiff.v1", "code": change_code, "channel": channel, "page_id": page_id, "subject_ids": list(key), "expected": exp[key], "observed": obs[key]})
    return missing, additional, changed


def compare_semantics(
    expected_xml: bytes,
    observed_xml: bytes,
    expected_contract: Json,
    observed_provenance: Json,
    *,
    checker_version: str = "1.0.0",
) -> Json:
    expected_info: Json = {
        "decision_ref": expected_contract.get("decisionRef"),
        "decision_id": expected_contract.get("decisionId"),
        "release_id": expected_contract.get("releaseId"),
        "adrs_merge_commit": expected_contract.get("adrsMergeCommit"),
        "accepted_at": expected_contract.get("acceptedAt"),
        "accepted_artifact_sha256": sha256_bytes(expected_xml),
    }
    observed_info: Json = {
        "implementation_revision": observed_provenance.get("implementationRevision"),
        "implementation_source_digest": observed_provenance.get("implementationSourceDigest"),
        "generator_digest": observed_provenance.get("generatorDigest"),
        "generated_artifact_sha256": sha256_bytes(observed_xml),
        "generated_at": observed_provenance.get("generatedAt"),
        "origin": observed_provenance.get("origin"),
    }
    policy = expected_contract.get("policy")
    if not isinstance(policy, dict):
        policy = {}
    policy_digest = sha256_json(policy)
    base: Json = {
        "kind": "diagram.conformance.v1",
        "expected": expected_info,
        "observed": observed_info,
        "engine": {"checker_version": checker_version, "policy_digest": policy_digest},
        "comparison": {"status": "ERROR", "missing": [], "additional": [], "changed": [], "visual_only": [], "errors": []},
        "authority": False,
    }
    errors: list[Json] = []
    try:
        required_contract = (
            "decisionRef", "decisionId", "releaseId", "adrsMergeCommit", "acceptedAt",
            "acceptedArtifactSha256", "expectedSemanticSha256", "pageIds", "stableSubjectIds",
            "policy", "policyCanonicalDigest", "acceptedDecisionCanonicalDigest",
        )
        for key in required_contract:
            if key not in expected_contract:
                raise ConformanceInputError("MISSING_PROVENANCE", f"expected contract missing: {key}")
        if re.fullmatch(r"[0-9a-f]{40}", str(expected_contract["adrsMergeCommit"])) is None:
            raise ConformanceInputError("MISSING_PROVENANCE", "exact ADRS merge commit required")
        if not str(expected_contract["decisionId"]) or not str(expected_contract["releaseId"]):
            raise ConformanceInputError("MISSING_PROVENANCE", "Decision and release identities required")
        if expected_contract["acceptedArtifactSha256"] != sha256_bytes(expected_xml):
            raise ConformanceInputError("EXPECTED_ARTIFACT_DIGEST_MISMATCH", "expected artifact digest mismatch")
        if expected_contract["policyCanonicalDigest"] != sha256_json(policy):
            raise ConformanceInputError("EXPECTED_POLICY_DIGEST_MISMATCH", "accepted policy digest mismatch")
        if policy.get("implicitToleranceAllowed") is not False:
            raise ConformanceInputError("UNKNOWN_POLICY", "implicit tolerance must be forbidden")
        required_observed = (
            "implementationRevision", "implementationSourceDigest", "generatorDigest",
            "generatedArtifactSha256", "generatedAt", "origin", "expectedContentSourceUsed",
        )
        for key in required_observed:
            if key not in observed_provenance:
                raise ConformanceInputError("MISSING_PROVENANCE", f"observed provenance missing: {key}")
        if re.fullmatch(r"[0-9a-f]{40}", str(observed_provenance["implementationRevision"])) is None:
            raise ConformanceInputError("MISSING_PROVENANCE", "exact implementation revision required")
        for key in ("implementationSourceDigest", "generatorDigest", "generatedArtifactSha256"):
            if re.fullmatch(r"sha256:[0-9a-f]{64}", str(observed_provenance[key])) is None:
                raise ConformanceInputError("MISSING_PROVENANCE", f"exact digest required: {key}")
        if not isinstance(observed_provenance.get("generatedAt"), str) or not observed_provenance["generatedAt"]:
            raise ConformanceInputError("MISSING_PROVENANCE", "generatedAt required")
        if observed_provenance.get("origin") != "implementation-derived":
            raise ConformanceInputError("OBSERVED_ORIGIN_INVALID", "observed origin must be implementation-derived")
        if observed_provenance.get("expectedContentSourceUsed") is not False:
            raise ConformanceInputError("EXPECTED_CONTENT_SOURCE_REUSED", "observed generation used expected content")
        if observed_provenance["generatedArtifactSha256"] != sha256_bytes(observed_xml):
            raise ConformanceInputError("OBSERVED_ARTIFACT_DIGEST_MISMATCH", "observed artifact digest mismatch")

        expected_pages = parse_mxfile(expected_xml)
        observed_pages = parse_mxfile(observed_xml)
        expected_selection = semantic_selection(expected_pages, policy)
        observed_selection = semantic_selection(observed_pages, policy)
        expected_semantic = sha256_json(expected_selection)
        observed_semantic = sha256_json(observed_selection)
        expected_info["semantic_sha256"] = expected_semantic
        observed_info["semantic_sha256"] = observed_semantic
        if expected_contract["expectedSemanticSha256"] != expected_semantic:
            raise ConformanceInputError("EXPECTED_SEMANTIC_DIGEST_MISMATCH", "expected semantic digest mismatch")
        if sorted(expected_contract["pageIds"]) != sorted(expected_pages):
            raise ConformanceInputError("EXPECTED_PAGE_IDENTITY_MISMATCH", "expected page IDs do not match artifact")
        actual_subject_ids = sorted(f"{pid}:{sid}" for pid, page in expected_pages.items() for sid in page.subjects)
        if sorted(expected_contract["stableSubjectIds"]) != actual_subject_ids:
            raise ConformanceInputError("EXPECTED_SUBJECT_IDENTITY_MISMATCH", "expected subject IDs do not match artifact")

        missing: list[Json] = []
        additional: list[Json] = []
        changed: list[Json] = []
        expected_page_map = {page["id"]: page for page in expected_selection["pages"]}
        observed_page_map = {page["id"]: page for page in observed_selection["pages"]}
        for page_id in sorted(expected_page_map.keys() - observed_page_map.keys()):
            missing.append({"kind": "diagram.semanticDiff.v1", "code": "missing_expected", "channel": "page", "page_id": page_id, "subject_ids": [], "expected": expected_page_map[page_id], "observed": None})
        for page_id in sorted(observed_page_map.keys() - expected_page_map.keys()):
            additional.append({"kind": "diagram.semanticDiff.v1", "code": "unapproved_observed", "channel": "page", "page_id": page_id, "subject_ids": [], "expected": None, "observed": observed_page_map[page_id]})
        for page_id in sorted(expected_page_map.keys() & observed_page_map.keys()):
            m, a, c = _diff_page(expected_page_map[page_id], observed_page_map[page_id])
            missing.extend(m); additional.extend(a); changed.extend(c)

        expected_visual = visual_selection(expected_pages)
        observed_visual = visual_selection(observed_pages)
        visual_only = [] if expected_visual == observed_visual else [{"code": "visual_only_changed", "expectedSha256": sha256_json(expected_visual), "observedSha256": sha256_json(observed_visual)}]
        status = "PASS" if not missing and not additional and not changed else "FAIL"
        base["comparison"] = {
            "status": status,
            "missing": missing,
            "additional": additional,
            "changed": changed,
            "visual_only": visual_only,
            "errors": [],
        }
    except ConformanceInputError as exc:
        errors.append({"code": exc.code, "message": str(exc)})
        base["comparison"]["errors"] = errors
        base["comparison"]["status"] = "ERROR"
    except Exception as exc:  # fail closed for unexpected comparator failures
        errors.append({"code": "COMPARATOR_EXCEPTION", "message": f"{type(exc).__name__}: {exc}"})
        base["comparison"]["errors"] = errors
        base["comparison"]["status"] = "ERROR"
    return base


def receipt_bytes(receipt: Json) -> bytes:
    return (canonical_json(receipt) + "\n").encode("utf-8")


def load_json(path: Path) -> Json:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: object required")
    return value
