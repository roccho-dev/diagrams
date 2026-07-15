# wt-023 semantic roundtrip kernel

Issue: #2

This worktree adds the first executable PoC for the editable semantic roundtrip kernel.

## Purpose

Prove the irreversible boundary:

```text
events.jsonl -> reducer -> DVM -> projection/editor command -> JSONL append -> re-reduce -> proof
```

The PoC is intentionally UI-free. It does not create a canvas/editor. It proves the semantic write-back kernel that a React Flow, GLSP, draw.io, BPMN, or Gantt adapter can later call.

## What changed

| Area | Change |
|---|---|
| Plane taxonomy | add `LaneProgressPlane`, `GraphPlane`, `TablePlane`, `RegionPlane` classifier |
| Edit roundtrip | add editor-independent `EditCommand` translator |
| Event schema | add semantic update and visual patch events |
| Reducer | apply label, reconnect, lane, span, and visual patch events |
| Proof | add semantic/visual hash split and roundtrip proof |
| Fixtures | add triptych, graph, visual isolation, table/region boundary PoC builder |
| CI | run tests and build semantic roundtrip PoC before artifact upload |

## Why this is better than the old implementation

The previous implementation already generated SVG/drawio artifacts from JSONL. That was useful, but one-way.

This PoC is a higher-level boundary proof:

| Old | New |
|---|---|
| JSONL -> generated artifacts | JSONL -> DVM -> edit command -> JSONL append -> proof |
| diagram kind selects layout backend | diagram kind maps to semantic Plane/Profile/Rules |
| generated artifact can be viewed | semantic and visual edits can be proven separately |
| layout proof only | semantic write-back proof |
| diagram-specific pressure | shared LaneProgressPlane / GraphPlane / TablePlane / RegionPlane |

## Acceptance evidence

Local proof command:

```sh
python -m unittest discover -s tests -v
python tools/build_semantic_roundtrip_poc.py --out /tmp/semantic-roundtrip
```

The PoC passes only if:

- lane-progress triptych uses one DVM for swimlane/gantt-like/horizontal-sequence projection fingerprints.
- graph reconnect appends `edge.reconnect` and invalid reconnect is rejected before append.
- visual movement changes visual hash but not semantic hash.
- ERD maps to TablePlane and Venn maps to RegionPlane without new engines.
- core imports no editor or layout dependency.
