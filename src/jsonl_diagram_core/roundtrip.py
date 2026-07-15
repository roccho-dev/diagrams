from __future__ import annotations

from copy import deepcopy
from typing import Any

from .io import canonical_json, sha256_text
from .planes import projection_fingerprint
from .reducer import reduce_tokens
from .tokenizer import tokenize_events

JsonObj = dict[str, Any]

SEMANTIC_COMMANDS = {
    "RenameNode",
    "RenameEdge",
    "ReconnectEdge",
    "ConnectEdge",
    "MoveToLane",
    "ChangeSpan",
}
VISUAL_COMMANDS = {
    "MoveNodeVisual",
    "SetEdgeBendpoint",
}


def _clean_dvm(dvm: JsonObj) -> JsonObj:
    out = deepcopy(dvm)
    for key in ("hash",):
        out.pop(key, None)
    return out


def semantic_projection(dvm: JsonObj) -> JsonObj:
    out = _clean_dvm(dvm)
    out.pop("visualPatches", None)
    return out


def visual_projection(dvm: JsonObj) -> JsonObj:
    return {"visualPatches": deepcopy(dvm.get("visualPatches", []))}


def semantic_hash(dvm: JsonObj) -> str:
    return "sha256:" + sha256_text(canonical_json(semantic_projection(dvm)))


def visual_hash(dvm: JsonObj) -> str:
    return "sha256:" + sha256_text(canonical_json(visual_projection(dvm)))


def _diff_paths(a: Any, b: Any, prefix: str = "") -> list[str]:
    if type(a) is not type(b):
        return [prefix or "$root"]
    if isinstance(a, dict):
        paths: list[str] = []
        for key in sorted(set(a) | set(b)):
            p = f"{prefix}.{key}" if prefix else str(key)
            if key not in a or key not in b:
                paths.append(p)
            else:
                paths.extend(_diff_paths(a[key], b[key], p))
        return paths
    if isinstance(a, list):
        if len(a) != len(b):
            return [prefix or "$root"]
        paths: list[str] = []
        for i, (left, right) in enumerate(zip(a, b)):
            paths.extend(_diff_paths(left, right, f"{prefix}[{i}]"))
        return paths
    return [] if a == b else [prefix or "$root"]


def reduce_events(events: list[JsonObj]) -> JsonObj:
    return reduce_tokens(tokenize_events(events))


def event_from_command(command: JsonObj) -> JsonObj:
    ctype = command.get("type")
    cid = command.get("commandId")
    if ctype in {"RenameNode", "RenameEdge"}:
        return {
            "op": "label.update",
            "target": command["targetId"],
            "label": command["value"],
            "sourceCommandId": cid,
        }
    if ctype == "ReconnectEdge":
        return {
            "op": "edge.reconnect",
            "id": command["edgeId"],
            "source": command["source"],
            "target": command["target"],
            "sourceCommandId": cid,
        }
    if ctype == "ConnectEdge":
        return {
            "op": "edge.upsert",
            "id": command["edgeId"],
            "source": command["source"],
            "target": command["target"],
            "label": command.get("label", ""),
            "sourceCommandId": cid,
        }
    if ctype == "MoveToLane":
        return {
            "op": "lane.assign",
            "id": command["targetId"],
            "lane": command["laneId"],
            "sourceCommandId": cid,
        }
    if ctype == "ChangeSpan":
        return {
            "op": "span.update",
            "id": command["targetId"],
            "start": command["start"],
            "end": command["end"],
            "sourceCommandId": cid,
        }
    if ctype == "MoveNodeVisual":
        event = {
            "op": "visual.position.set",
            "target": command["targetId"],
            "x": command["x"],
            "y": command["y"],
            "sourceCommandId": cid,
        }
        if "lock" in command:
            event["lock"] = bool(command["lock"])
        return event
    if ctype == "SetEdgeBendpoint":
        return {
            "op": "visual.edge.bendpoint.set",
            "id": command["edgeId"],
            "points": command.get("points", []),
            "sourceCommandId": cid,
        }
    raise ValueError(f"unsupported command type: {ctype}")


def apply_edit_command(events: list[JsonObj], command: JsonObj, *, projection_profiles: list[str] | None = None) -> JsonObj:
    before_dvm = reduce_events(events)
    event = event_from_command(command)
    after_events = [*events, event]
    after_dvm = reduce_events(after_events)
    profiles = projection_profiles or []
    parity = {
        profile: projection_fingerprint(after_dvm, profile=profile)
        for profile in profiles
    }
    proof: JsonObj = {
        "schema": "SemanticRoundtripProof.v1",
        "authority": "events.jsonl",
        "generatedIsAuthority": False,
        "accepted": True,
        "editCommand": command,
        "appendedEvent": event,
        "appendedEventHash": "sha256:" + sha256_text(canonical_json(event)),
        "dvmBeforeHash": before_dvm["hash"],
        "dvmAfterHash": after_dvm["hash"],
        "semanticHashBefore": semantic_hash(before_dvm),
        "semanticHashAfter": semantic_hash(after_dvm),
        "visualHashBefore": visual_hash(before_dvm),
        "visualHashAfter": visual_hash(after_dvm),
        "semanticDiff": {
            "paths": _diff_paths(semantic_projection(before_dvm), semantic_projection(after_dvm)),
        },
        "visualDiff": {
            "paths": _diff_paths(visual_projection(before_dvm), visual_projection(after_dvm)),
        },
        "projectionParity": parity,
        "adapterBoundary": {"coreImportsAdapter": False, "adapterImportsCore": True},
    }
    proof["proofSha256"] = "sha256:" + sha256_text(canonical_json(proof))
    return {"events": after_events, "dvm": after_dvm, "proof": proof}


def reject_edit_command(events: list[JsonObj], command: JsonObj) -> JsonObj:
    before_dvm = reduce_events(events)
    event: JsonObj | None = None
    try:
        event = event_from_command(command)
        reduce_events([*events, event])
    except Exception as exc:
        proof: JsonObj = {
            "schema": "SemanticRoundtripProof.v1",
            "authority": "events.jsonl",
            "generatedIsAuthority": False,
            "accepted": False,
            "editCommand": command,
            "candidateEvent": event,
            "error": str(exc),
            "dvmBeforeHash": before_dvm["hash"],
            "semanticHashBefore": semantic_hash(before_dvm),
            "visualHashBefore": visual_hash(before_dvm),
            "appended": False,
        }
        proof["proofSha256"] = "sha256:" + sha256_text(canonical_json(proof))
        return proof
    raise AssertionError("command unexpectedly accepted")
