# mxGraphModel direct-current-state proof

## Decision under test

Eliminate the repository-specific DVM and rendering-IR boundaries rather than renaming them.

Retained contracts:

- `events.jsonl` remains the only authority and append history;
- validation happens before append;
- semantic and visual edits remain separable;
- semantic current-state fields and domain metadata survive; operation provenance remains in `events.jsonl`;
- native draw.io stays editable;
- SVG, image-exact draw.io, D2, Graphviz, text and geometry checks reuse the same current state.

## Candidate boundary

```text
events.jsonl
  -> validate + reduce
  -> mxGraphModel XML
  -> draw.io / SVG / image draw.io / D2 / Graphviz / text / metrics
```

There is no public or persisted independent current-state format between events and `mxGraphModel`.
The reducer uses ordinary local maps only while applying append-order events, then emits `mxGraphModel` directly.
Semantic data is stored in draw.io XML user objects wrapping `mxCell`; geometry, graph links and style remain on `mxCell`/`mxGeometry`.

## Safety rules proved locally

- semantic IDs are globally unique across diagram, group, node and edge;
- an edge endpoint can never be selected by map overwrite order;
- terminal-connected edges without explicit endpoints are `inferred`, never `exact`;
- `require_exact_edges=True` fails closed on inferred edge paths;
- required proof files and every manifest entry are checked before proof success;
- the proof implementation must be deleted or absorbed into canonical tests during cutover.

## Run

```text
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python tools/build_proof.py
python tools/verify_required_evidence.py --root .
python tools/audit_proposal_readiness.py \
  --candidate . \
  --baseline ../diagrams-ci \
  --out validation/local-preflight.json
```

## Local result

- Current canonical CI evidence: 49 tests, 13 SVG/native draw.io/image-exact sample sets and 4 roundtrip fixtures pass.
- Direct-current-state proof: 37 tests pass.
- All 15 event operations and eight editor command forms are covered; sourceCommandId is validated and remains event provenance rather than duplicated model state.
- 13 diagram-kind fixtures build all projections without DVM, RenderAst or RenderingIR.
- Every initial event field is checked against resulting XML user-object/cell state.
- A simulated editor normalization strips custom data from nested `mxCell`; semantic recovery and semantic hash remain stable from the user object.
- The source exports no custom `*IR` or snapshot API.
- No independent semantic/current-state JSON artifact is emitted.
- Current canonical Venn native draw.io drops `meta.members`; the candidate preserves every Venn membership in `metaJson` on XML user objects.
- All 24 generated terminal-connected edge paths are reported as inferred; no false model-exact edge claim remains.
- Proof artifact collection is self-contained and fail-closed.

## Status boundary

```text
local mechanism preflight          PASS
merge readiness                    NOT_PASSED
architecture decision acceptance   NOT_RUN
exact canonical DVM cutover         NOT_RUN
```

The local result proves the mechanism and the revised failure oracles. It does not authorize merge. Merge still requires an accepted decision, independent review, the revised exact-head CI, and a clean/squashed submission. Canonical cutover remains a separate PR.
