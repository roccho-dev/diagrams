# wt-022-ci-artifact-gallery

## Goal

Make the canonical `proposals` branch visible and checkable from GitHub Actions.

## Scope

- Add a GitHub Actions workflow.
- Run the existing Python test suite.
- Validate generated SVG / native drawio / image-exact drawio artifacts.
- Build a directly openable `index.html` gallery.
- Upload the gallery, SVG files, drawio files, manifest, and quality report as a workflow artifact.

## canonTDD completion rule

Red:

- CI has no artifact-gallery workflow.
- Missing SVG/drawio artifacts are not caught by CI.
- No directly openable HTML gallery exists in CI output.

Green:

- `.github/workflows/artifact-gallery.yml` runs on PRs to `proposals`, pushes to `proposals`, and manual dispatch.
- `python -m unittest discover -s tests -p 'test_*.py'` runs in CI.
- `tools/build_ci_artifact_gallery.py` parses all SVG and drawio XML artifacts.
- `ci-artifacts/diagram-gallery/index.html` is generated.
- `actions/upload-artifact` uploads `diagram-artifact-gallery`.

Refactor boundary:

- Do not change canonical JSONL model.
- Do not change generated diagram outputs.
- This worktree is CI visibility only.
