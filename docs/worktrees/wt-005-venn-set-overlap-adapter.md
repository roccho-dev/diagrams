# wt-005-venn-set-overlap-adapter: venn set overlap adapter

## scope
集合/重なりをgraph layoutに寄せない

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_005_venn_set_overlap_adapter.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/venn_layout.py |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
