# MP-JSONL-DIAGRAM-CORE-VENN-260614

Status: ready for canonical merge-proposal review, subject only to the external Nix gates that cannot run in this sandbox.

## Merge posture

- Base: `canonical-core-proposal-package.resolved.zip` / canonical main worktree.
- Branch/worktree name: `proposal/jsonl-diagram-core-venn-260614`.
- Target repo: `modeldraw-ir`.
- Authority: `events.jsonl` only.
- Generated assets: evidence/proof only; never authority.
- Package surface: explicit `packages.<system>.jsonl-diagram-core`; no `default` package/app exposure.
- Core boundary: `src/jsonl_diagram_core` imports no adapter fixture code.

## Semantic no-regression repairs

1. `entity.upsert.kind` is preserved. ERD table entities reduce to DVM nodes with `kind: "table"`, plus `opClass: "entity"` and `entityKind: "table"` annotations. Adapters render SQL-table shape from `opClass` / `entityKind` / `meta.columns`, not by overwriting source kind.
2. The dense dependency edge ID `d2` is preserved exactly. The core validator now treats node IDs and edge IDs as separate DVM namespaces, while rejecting ambiguous style/layout targets when a raw string exists in both namespaces.
3. Append order is preserved as a semantic tie-breaker when explicit `order` is absent. This prevents lexicographic edge sorting from changing dense dependency order.

## Proof gates run in this package

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -v
npm ci --no-audit --no-fund --ignore-scripts
PYTHONPATH=src:. python examples/expression_suite/build_suite.py --out generated/expression-suite --require-engines
PYTHONPATH=src:. python tools/check_generated_svg.py generated/expression-suite
python tools/semantic_compare_legacy.py --legacy <legacy-samples> --current generated/expression-suite/samples --require-dvm --report proposal-evidence/legacy-semantic-compare.json
node examples/expression_suite/tools/d2_elk_smoke.mjs generated/expression-suite
PYTHONPATH=src:. python tools/rebuild_compare.py --expected generated/expression-suite --require-engines --run-d2-elk-smoke
python -m pip wheel . -w <wheelhouse> --no-deps --no-build-isolation
python tools/check_no_html_in_zip.py <submission-zip>
```

`nix` is not installed in this sandbox, so `nix build .#jsonl-diagram-core` and `nix flake check` remain mandatory external CI gates.

## Validation summary

See `validation/` for command logs and JSON reports. The legacy semantic comparison passes for all 12 baseline samples across both source-event and DVM layers. The added `13_venn` sample is reported as a new allowed sample and does not change legacy semantics.
