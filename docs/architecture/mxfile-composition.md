# Deterministic multi-page mxfile composition

## Decision

Compose already-generated, native single-page draw.io documents into one ordered multi-page `mxfile` without introducing another document model.

```text
single-page mxfile[]
  -> validate all inputs
  -> copy ordered diagram[]
  -> deterministic multi-page mxfile
```

Each input `mxGraphModel` is opaque. The composer does not read events, reduce state, lay out nodes, route edges, or interpret Timeline/Overlay semantics.

## Input contract

Every input is valid XML with:

- root `mxfile`
- zero or false `compressed` state
- exactly one direct `diagram`
- non-empty `diagram.id`
- non-empty `diagram.name`
- exactly one direct, uncompressed `mxGraphModel`

At least one input is required. Duplicate page IDs are rejected. Page names may repeat. DTD and entity declarations are rejected before model parsing, independent of UTF-8 or UTF-16 input encoding.

## Output contract

The output:

- has one `mxfile` root
- has only stable root attributes: `compressed="false"` and actual `pages`
- contains one copied `diagram` per input
- preserves input order
- preserves each diagram's attributes and complete `mxGraphModel` subtree
- contains no wall-clock metadata
- is byte-identical for identical ordered inputs
- is written atomically only after all inputs and the completed output pass verification

The implementation compares structural SHA-256 digests for every input/output diagram and `mxGraphModel`. Attribute order and indentation-only whitespace are not semantic; element order, attributes, meaningful text, and all descendants are semantic.

## Failure model

All contract violations fail closed. Invalid input cannot create a new output, replace an existing output, or leave a temporary file. Output verification rejects page reorder, page identity changes, cell/attribute/geometry/user-object mutation, or model removal.

## Authority boundary

`mxfile` is the native draw.io outer document. This proof adds no `DocumentIR`, `PageIR`, event authority, JSONL reducer, or canonical current-state model.

```text
events.jsonl / existing producer
  -> single-page mxfile[]
  -> this composer
  -> multi-page mxfile
```

Only the last arrow is owned here.

## Executable proof

`proposal-evidence/mxfile-composition/run_all.sh` performs:

1. standard-library unit tests
2. 1-, 2-, and 5-page positive compositions
3. 15 required destructive cases
4. opaque model structural-digest checks
5. two independent full proof replays
6. byte comparison of all replay artifacts
7. comparison with the committed deterministic summary
8. SHA-256 manifest verification
9. clean-tree verification when run from Git

The deterministic summary contains no commit SHA, run ID, clock, or absolute path. CI creates a separate execution receipt bound to the checked-out commit, proof bytes, Python runtime, and runner platform.

## CI lifecycle

The dedicated workflow has two pull-request checks:

- **exact head**: checks out the PR head SHA, enforces the changed-path allowlist (including both sides of renames), replays the proof, and emits a CI receipt
- **integration**: creates a local merge of the event's base SHA and exact PR head, then replays the same proof

After merge, a `push` run on `proposals` checks the actual merged commit and emits a post-merge receipt. Issue closure remains separate from PR merge until that post-merge run is green. Third-party Actions are pinned to immutable release commit SHAs.

## Non-goals

This proof does not add:

- JSONL reading or writing
- event operations or reducers
- `mxGraphModel` construction or mutation
- Timeline/Overlay semantics or condition evaluation
- page CRUD or Embed API use
- browser JavaScript
- compression or viewer URL generation
- layout, routing, rendering, or geometry checking
- cross-page link authoring or rewriting
- canonical package integration or publication
