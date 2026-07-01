# wt-009-svg-renderer: SVG renderer

## scope
render ASTからSVGを出す

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_009_svg_renderer.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/svg_render_ast.py |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
