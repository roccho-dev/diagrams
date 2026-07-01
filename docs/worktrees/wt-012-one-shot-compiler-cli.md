# wt-012-one-shot-compiler-cli: one-shot compiler CLI

## scope
JSONLから成果物一式を一発生成する

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_012_one_shot_compiler_cli.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/one_shot.py, src/jsonl_diagram_core/cli.py |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
