# wt-011-drawio-image-mode-renderer: drawio image mode renderer

## scope
SVG完全見た目用drawio image modeを出す

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_011_drawio_image_mode_renderer.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/drawio_image_mode.py |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
