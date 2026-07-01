# wt-007-network-projection-adapter: network projection adapter

## scope
networkを目的別にDAG視点/force視点へ分ける

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_007_network_projection_adapter.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/network_projection.py |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
