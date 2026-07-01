# wt-003-layout-router-contract: layout router contract

## scope
図タイプごとにlayout backendを選ぶ契約を置く

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_003_layout_router_contract.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/layout_router.py |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
