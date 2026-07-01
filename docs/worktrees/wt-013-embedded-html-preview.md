# wt-013-embedded-html-preview: embedded HTML preview

## scope
websandbox不要HTMLを生成する

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_013_embedded_html_preview.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/embedded_preview.py |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
