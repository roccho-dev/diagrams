# Integration Report: Venn Expression Coverage

Integrated from `260614-065900-venn-expression-coverage.zip` over the refactor-contract line.

Included:

- Core/schema hardening from the Venn branch.
- Stable adapter-id mapping changes for D2/DOT fixture adapters.
- Rebuild-compare proof gate.
- `13_venn` expression-suite fixture and generated artifacts.
- Packaged schema under `src/jsonl_diagram_core/schemas`.

Excluded from this cleaned worktree package:

- `build/`
- `dist/`
- `*.egg-info/`
- `node_modules/`
- `__pycache__/`
- stale `zip-check-result.json`

Recommended commit split:

1. core/schema hardening
2. adapter/proof hardening
3. Venn expression coverage
4. docs/reports
