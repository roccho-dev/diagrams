# Canonical cutover change map

| Current path/surface | Required change |
|---|---|
| `src/jsonl_diagram_core/reducer.py` | emit `mxGraphModel` directly; no `DiagramViewModel.v1` |
| `src/jsonl_diagram_core/schema.py` | remove `DvmValidationError`/`validate_dvm`; validate semantic user objects and native graph references |
| `src/jsonl_diagram_core/ports.py` | projection ports accept `mxGraphModel`, never `dvm` dictionaries |
| `src/jsonl_diagram_core/cli.py` | remove DVM JSON output; expose check/compile/model output only |
| `src/jsonl_diagram_core/roundtrip.py` | semantic/visual selections and diffs come from `mxGraphModel` |
| `src/jsonl_diagram_core/planes.py` | classify from semantic user-object fields |
| `src/jsonl_diagram_core/one_shot.py` | remove `dvm_to_simple_render_ast`; project the model directly |
| `src/jsonl_diagram_core/render_ast.py` | delete |
| `src/jsonl_diagram_core/drawio_render_ast.py` | delete |
| `src/jsonl_diagram_core/svg_render_ast.py` | delete after direct model projection |
| `examples/adapters/*` | consume `mxGraphModel`; preserve stable semantic IDs |
| `examples/expression_suite/build_suite.py` | do not emit `dvm.json`; emit model/proof only |
| `tests/e2e/test_fixtures.py` | replace DVM artifact assertions with semantic-model completeness and projection parity |
| proof/provenance | replace `dvmHash` with semantic/visual model hashes |
| docs/Issue #2/#4/#5 | supersede DVM/RenderingIR ownership, retain event/proof contracts |
| generated fixtures | remove every `dvm.json` and independent current-state artifact |
| CI | add no-duplicate-IR, exact fixture, Nix, pinned editor and exact-head gates |

## Delete gate

The cutover is incomplete while any production source, schema, fixture, CLI, proof field or normative document contains DVM/RenderAst/RenderingIR as a current-state contract.

## Proof retirement gate

The cutover PR must remove `proposal-evidence/dvm-elimination/src/mxgraph_core` and `proposal-evidence/dvm-elimination/tools/build_proof.py`, or first move their unique tests into the canonical suite and then delete the duplicate runtime. Evidence documents may remain; a second reducer or projection implementation may not.
