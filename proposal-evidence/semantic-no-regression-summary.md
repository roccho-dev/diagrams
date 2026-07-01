# Semantic no-regression summary

The semantic authority is `events.jsonl`. The regression gate compares the 12 legacy samples from `260614-104854.zip` against the current generated suite at two layers:

1. authority event semantics; and
2. generated DVM semantics.

Result: pass. No legacy sample has a semantic failure. `13_venn` is an additive fixture only.

Key repairs:

- `07_erd`: `entity.upsert.kind` remains `table` in DVM. Entity role is carried separately by `opClass: "entity"` and `entityKind: "table"`.
- `09_dense_dependency`: edge ID `d2` is preserved exactly even though node ID `d2` also exists. Node and edge IDs are separate namespaces; ambiguous style/layout targets are rejected.
- Missing explicit `order` now uses append order as the tie-breaker, matching the declared `eventOrdering: append-order` policy.
