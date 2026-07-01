# wt-002-jsonl-meaning-model: JSONL meaning model

## scope
図面座標ではなく意味モデルを正本にする

## kentbeck-canonTDD completion

| phase | evidence |
|---|---|
| red | acceptance test added before completion: tests/canontdd/test_002_jsonl_meaning_model.py |
| green | minimal production/proposal change: src/jsonl_diagram_core/meaning_model.py, schemas/diagram-meaning.v1.schema.json |
| refactor | boundary kept: core does not import adapters; generated artifacts are not authority |
| done | `python -m unittest discover -s tests -v` passes in this worktree |
