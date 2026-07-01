# wt-010-drawio-native-renderer: drawio native renderer

## scope
render ASTから編集可能drawioを出す

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_010_drawio_native_renderer.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/drawio_render_ast.py |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
