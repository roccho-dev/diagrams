# diagrams

Deterministic diagram compilation and review tooling.

## Authority

```text
ADRS Accepted Decision             architecture authority
events.jsonl                       diagram-event authority and append history
mxGraphModel / mxfile              sole generated current state
SVG / D2 / Graphviz / image view   non-authority projections
receipts / screenshots             non-authority evidence
```

## Canonical flow

```text
events.jsonl
  -> strict event and reference validation
  -> transient reducer maps
  -> XML user objects + mxCell + mxGeometry
  -> mxGraphModel
  -> projections / editor / checks / receipts
```

Semantic IDs are globally unique across diagram, group, node, and edge objects. Invalid references and edit commands fail before append. Semantic and visual hashes are independently derived from the same model.

## Commands

```text
jsonl-diagram-core check events.jsonl
jsonl-diagram-core reduce events.jsonl --out model.drawio
jsonl-diagram-core compile-bundle events.jsonl --out-dir out
```

## Checks

- all unit, destructive, fixture, editor, and approval-receipt tests;
- 13 canonical JSONL logs generate 13 `model.drawio` files;
- SVG, D2, Graphviz and image projections are derived from those models;
- deterministic clean rebuild;
- no public or persistent independent current-state model;
- `nix flake check` and package build.

Generated outputs never become accepted meaning authority.
