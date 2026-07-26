# Target architecture

## Package graph

```text
event_contract
  -> mxgraph_reducer
  -> mxgraph_projection

edit_command
  -> event_contract

mxgraph_projection
  -> svg
  -> d2
  -> graphviz_elk
  -> drawio
  -> text
  -> geometry_audit
```

No package between `mxgraph_reducer` and projections owns another current-state schema.

## Data flow

```text
events.jsonl
  -> validate
  -> transient maps while reducing
  -> XML user objects + mxCell + mxGeometry
  -> mxGraphModel
  -> projections / editor / proof / metrics

editor change
  -> normalized command
  -> validate against mxGraphModel
  -> append one event
  -> re-reduce
  -> semantic + visual proof
```

## Identity invariant

```text
semantic ID namespace = global
```

A raw ID belongs to exactly one of diagram, group, node or edge. Re-upsert inside the same namespace is allowed. Cross-namespace reuse is rejected before reduction. Edge endpoints therefore resolve to exactly one group or node and can never bind through dictionary overwrite order.

## Edge precision invariant

```text
explicit = sourcePoint + targetPoint are present
inferred = one or both endpoints come from terminal-center estimation
rendered = reserved for a fixed renderer's final path
```

Inferred paths may produce advisory UI findings but never model-exact claims. A policy that requires exact edge paths rejects inferred paths.

## Ownership

| Data | Owner | Persisted |
|---|---|---:|
| Event history | `events.jsonl` | yes, authority |
| Current meaning + graph + geometry | generated `mxGraphModel` | yes, non-authority |
| Reducer maps | reducer function | no |
| Projection-specific objects | projection function | no |
| Proof receipts | CI | yes, evidence |

## XML encoding

```xml
<object jsonlId="..." semanticKind="..." metaJson="{...}">
  <mxCell parent="..." source="..." target="...">
    <mxGeometry ... />
  </mxCell>
</object>
```

The wrapper is the draw.io XML user object. The nested cell is native graph state. This keeps semantics recoverable after editor normalization of `mxCell` attributes.

## Proof retirement

The proof package is temporary executable evidence, not a second production implementation. The canonical cutover must delete its reducer/projection runtime or absorb its tests and failure oracles into the canonical implementation. Two live reducers after cutover are forbidden.

## Provenance boundary

`sourceCommandId` identifies the append operation and remains in `events.jsonl`. It is validated but is not copied into `mxGraphModel`, because doing so would duplicate history in current state. Ports, source/target, labels, lanes, spans, geometry, locks, bendpoints, kinds and domain metadata are current-state fields and must be represented in the model.
