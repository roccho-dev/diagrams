# jsonl-diagram-contract-hardening

## Canonical merge-proposal readiness

This worktree includes `records/canonical-merge-proposal.jsonl`, `MERGE_PROPOSAL.md`, and validation evidence under `validation/` and `proposal-evidence/`. The proposal is ready for canonical review subject to external Nix CI, with no allowed semantic degradation.

Repairs made before submission:

- ERD `entity.upsert.kind` is preserved in DVM (`kind: "table"`); adapters use `opClass: "entity"` / `entityKind` / `meta.columns` for rendering.
- Dense dependency edge ID `d2` is preserved exactly by treating node and edge IDs as separate namespaces and rejecting ambiguous style/layout targets.
- Append order is preserved when explicit `order` is absent.

The legacy semantic gate compares the 12 baseline samples across both `events.jsonl` and generated DVM layers. `13_venn` is additive only.


This repository is a **Nix-packaged core + port library contract** plus **adapter e2e fixtures/examples**.

It is not prepared for npm or PyPI publication. The public boundary is:

- `src/jsonl_diagram_core`: pure core + port contracts.
- `src/jsonl_diagram_core/schemas`: packaged schema resources.
- `examples/adapters`: adapter examples and e2e fixture implementations.
- `tests/e2e/fixtures/adapters`: adapter fixture copies for tests.
- `examples/expression_suite`: Mermaid/draw.io-style expression coverage suite, including Venn coverage.
- `generated`: generated proof assets from JSONL only.

## Authority rule

Only `events.jsonl` is authoritative.

Generated artifacts are allowed only when they carry proof metadata and can be regenerated from JSONL.
HTML is preview-only and must not be included in the ZIP artifact.

## Refactor rule

Core does not import adapter code. Adapters import core.

```text
JSONL events -> tokenizer -> reducer -> DVM -> ports -> adapter fixtures/examples -> SVG proof artifacts
```

## Hardening added in this phase

- Runtime validator now matches the event schema more closely for `kind`, `intent`, `meta`, `order`, `start/end`, `columns`, and milestone timing.
- Reducer now performs DVM semantic validation for dangling edges and missing groups/lanes.
- D2/DOT fixture adapters now use injective stable adapter IDs, so `a-b` and `a_b` cannot collapse.
- Rebuild-compare proof gate regenerates the suite and compares hashes.
- Test discovery works via `python -m unittest discover -s tests -v`.
- Schema is included as package data under `jsonl_diagram_core.schemas`.

## Nix package output

The required Nix output is `packages.<system>.jsonl-diagram-core`.
It packages only the core+port library and schema resources, not adapter fixtures.

```sh
nix build .#jsonl-diagram-core
```

This container does not include the `nix` binary, so the flake is included but not executed here. `flake.lock` is not fabricated without `nix flake lock`.

## Local checks used here

```sh
python -m unittest discover -s tests -v
python -m pip wheel . -w /tmp/jsonl-diagram-wheelhouse --no-deps
npm ci --no-audit --no-fund --ignore-scripts
python examples/expression_suite/build_suite.py --out generated/expression-suite --require-engines
node examples/expression_suite/tools/d2_elk_smoke.mjs generated/expression-suite
python tools/check_generated_svg.py generated/expression-suite
python tools/rebuild_compare.py --expected generated/expression-suite --require-engines --run-d2-elk-smoke
python tools/check_no_html_in_zip.py <zip-file>
```

## Added Venn fixture

`examples/expression_suite/samples/13_venn/events.jsonl` proves Venn-style overlap diagrams from JSONL. It is an adapter fixture/example; core remains unchanged.
