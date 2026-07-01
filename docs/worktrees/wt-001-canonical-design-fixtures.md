# wt-001-canonical-design-fixtures: canonical design fixtures

## scope
既存デザインを検査可能なfixtureにする

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_001_canonical_design_fixtures.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/canonical_fixtures.py, canonical/fixtures/manifest.seed.json |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
