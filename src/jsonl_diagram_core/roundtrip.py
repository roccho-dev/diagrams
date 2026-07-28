from __future__ import annotations

from typing import Any

from .io import canonical_json, sha256_text
from .mxgraph_model import apply_command, build_model, command_to_event, semantic_hash, visual_hash
from .planes import projection_fingerprint

JsonObj = dict[str, Any]

SEMANTIC_COMMANDS = {"RenameNode", "RenameEdge", "ReconnectEdge", "ConnectEdge", "MoveToLane", "ChangeSpan"}
VISUAL_COMMANDS = {"MoveNodeVisual", "SetEdgeBendpoint"}


def reduce_events(events: list[JsonObj]) -> str:
    return build_model(events)


def event_from_command(command: JsonObj) -> JsonObj:
    return command_to_event(command)


def apply_edit_command(events: list[JsonObj], command: JsonObj, *, projection_profiles: list[str] | None = None) -> JsonObj:
    result = apply_command(events, command)
    if not result["proof"].get("accepted"):
        raise ValueError(result["proof"].get("error", "command rejected"))
    model = result["model"]
    event = result["proof"]["event"]
    proof: JsonObj = {
        "schema": "SemanticRoundtripProof.v2",
        "authority": "events.jsonl",
        "generatedIsAuthority": False,
        "accepted": True,
        "editCommand": command,
        "appendedEvent": event,
        "appendedEventHash": "sha256:" + sha256_text(canonical_json(event)),
        "modelBeforeHash": "sha256:" + sha256_text(build_model(events)),
        "modelAfterHash": "sha256:" + sha256_text(model),
        "semanticHashBefore": result["proof"]["semanticHashBefore"],
        "semanticHashAfter": result["proof"]["semanticHashAfter"],
        "visualHashBefore": result["proof"]["visualHashBefore"],
        "visualHashAfter": result["proof"]["visualHashAfter"],
        "projectionParity": {profile: projection_fingerprint(model, profile=profile) for profile in (projection_profiles or [])},
        "adapterBoundary": {"coreImportsAdapter": False, "adapterImportsCore": True},
    }
    proof["proofSha256"] = "sha256:" + sha256_text(canonical_json(proof))
    return {"events": result["events"], "model": model, "proof": proof}


def reject_edit_command(events: list[JsonObj], command: JsonObj) -> JsonObj:
    before = build_model(events)
    result = apply_command(events, command)
    if result["proof"].get("accepted"):
        raise AssertionError("command unexpectedly accepted")
    proof: JsonObj = {
        "schema": "SemanticRoundtripProof.v2",
        "authority": "events.jsonl",
        "generatedIsAuthority": False,
        "accepted": False,
        "editCommand": command,
        "candidateEvent": None,
        "error": result["proof"].get("error"),
        "modelBeforeHash": "sha256:" + sha256_text(before),
        "semanticHashBefore": semantic_hash(before),
        "visualHashBefore": visual_hash(before),
        "appended": False,
    }
    proof["proofSha256"] = "sha256:" + sha256_text(canonical_json(proof))
    return proof
