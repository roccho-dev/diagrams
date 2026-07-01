# wt-008-render-ast-contract: render AST contract

## scope
SVG/drawio共通の描画中間表現を置く

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_008_render_ast_contract.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/render_ast.py |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
