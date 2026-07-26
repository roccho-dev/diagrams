from __future__ import annotations

import argparse
import json
from pathlib import Path

from .io import canonical_json, read_jsonl, write_jsonl
from .tokenizer import tokenize_events
from .reducer import reduce_tokens


def _read_object(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return value


def _write_object(path: str | Path, value: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jsonl-diagram-core")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_check = sub.add_parser("check")
    p_check.add_argument("events")
    p_reduce = sub.add_parser("reduce")
    p_reduce.add_argument("events")
    p_reduce.add_argument("--out", required=True)
    p_tokens = sub.add_parser("tokens")
    p_tokens.add_argument("events")
    p_tokens.add_argument("--out", required=True)
    p_compile = sub.add_parser("compile-bundle")
    p_compile.add_argument("events")
    p_compile.add_argument("--out-dir", required=True)
    p_review = sub.add_parser("materialize-review")
    p_review.add_argument("semantic_drawio")
    p_review.add_argument("--policy", required=True)
    p_review.add_argument("--waivers", required=True)
    p_review.add_argument("--approval-receipts", required=True)
    p_review.add_argument("--repository", required=True)
    p_review.add_argument("--candidate-revision", required=True)
    p_review.add_argument("--as-of", required=True)
    p_review.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "materialize-review":
        from .decision_overlay import inspect_semantic_drawio, project_review_drawio
        from .policy_gate import gate_findings

        semantic_path = Path(args.semantic_drawio)
        semantic_text = semantic_path.read_text(encoding="utf-8")
        geometry = inspect_semantic_drawio(semantic_text)
        policy = _read_object(args.policy)
        waivers = read_jsonl(args.waivers)
        approval_receipts = read_jsonl(args.approval_receipts)
        report, gate_receipt = gate_findings(
            semantic_model_digest=geometry["semanticModelDigest"],
            verification=geometry["verification"],
            findings=geometry["findings"],
            policy=policy,
            waivers=waivers,
            approval_receipts=approval_receipts,
            repository=args.repository,
            candidate_revision=args.candidate_revision,
            as_of=args.as_of,
        )
        review_text, projection_receipt = project_review_drawio(
            semantic_text,
            report,
            gate_receipt,
            as_of=args.as_of,
        )
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "diagram.semantic.drawio").write_text(semantic_text, encoding="utf-8")
        (out / "diagram.review.drawio").write_text(review_text, encoding="utf-8")
        _write_object(out / "diagram.geometry.json", geometry)
        _write_object(out / "diagram.gate.json", report)
        _write_object(out / "diagram.gate-receipt.json", gate_receipt)
        _write_object(out / "diagram.projection-receipt.json", projection_receipt)
        print(canonical_json({
            "verification": report["verification"],
            "gateStatus": report["gateStatus"],
            "decision": report["decision"],
            "risk": report["risk"],
            "overlayCount": projection_receipt["overlayCount"],
        }))
        if report["gateStatus"] == "ERROR":
            return 4
        return {"ALLOW": 0, "REVIEW": 2, "DENY": 3}[report["decision"]]

    events = read_jsonl(args.events)
    tokens = tokenize_events(events)
    if args.cmd == "check":
        reduce_tokens(tokens)
        print(json.dumps({"ok": True, "events": len(events), "tokens": len(tokens)}, ensure_ascii=False))
        return 0
    if args.cmd == "tokens":
        write_jsonl(args.out, tokens)
        return 0
    if args.cmd == "reduce":
        dvm = reduce_tokens(tokens)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(dvm, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return 0
    if args.cmd == "compile-bundle":
        from .one_shot import compile_one_shot
        report = compile_one_shot(args.events, args.out_dir)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
