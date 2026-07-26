# Current state audit

## Accepted baseline evidence

The inspected GitHub Actions artifact contains:

- 49 passing tests;
- 13 SVG artifacts;
- 13 native draw.io artifacts;
- 13 image-exact draw.io artifacts;
- four accepted semantic-roundtrip fixtures.

| Sample | Nodes | Edges |
|---|---:|---:|
| 01_flow | 7 | 7 |
| 02_swimlane | 7 | 6 |
| 03_sequence | 6 | 8 |
| 04_state | 7 | 8 |
| 05_timeline | 8 | 0 |
| 06_gantt | 12 | 7 |
| 07_erd | 5 | 5 |
| 08_architecture | 10 | 11 |
| 09_dense_dependency | 14 | 21 |
| 10_nested_ports | 6 | 7 |
| 11_bpmn | 7 | 7 |
| 12_mindmap | 10 | 9 |
| 13_venn | 7 | 0 |

This proves the current DVM pipeline is healthy. It does not prove DVM deletion.

## Proven semantic loss in current native draw.io

The canonical Venn source defines seven region nodes with `meta.members`. The accepted native draw.io artifact:

- parses successfully;
- has stable `jsonlId` markers;
- has no XML user objects;
- has no `metaJson`;
- has no `members` value.

Therefore the native artifact cannot reconstruct exact Venn membership without returning to source events or inferring from geometry.

## Candidate difference

The no-DVM candidate encodes all seven membership lists in XML user objects and recovers them exactly after simulated editor-style `mxCell` normalization.

## Status

| Area | Status |
|---|---:|
| Current baseline audit | PASS |
| Direct model mechanism | PASS |
| Proposal readiness | PASS |
| Exact canonical cutover | NOT_RUN |
