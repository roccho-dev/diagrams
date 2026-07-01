from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from .io import canonical_json, read_jsonl, write_jsonl
from .tokenizer import tokenize_events
from .reducer import reduce_tokens


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
    args = parser.parse_args(argv)

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
