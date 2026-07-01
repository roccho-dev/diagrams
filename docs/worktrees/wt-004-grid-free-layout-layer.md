# wt-004-grid-free-layout-layer: grid + free layout layer

## scope
swimlane/wireframeを面配置として扱う

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_004_grid_free_layout_layer.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/grid_free_layout.py |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
