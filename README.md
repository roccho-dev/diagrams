# diagrams

Canonical JSONL diagram baseline for diagram generation.

## Current branch role

`main` is the baseline target for the completed `jsonl-diagram` work.

The completed local package is:

- `jsonl-diagram-quality-complete.260701-164418.zip`
- final local commit recorded in the package: `c78ca87`
- SVG quality gate: 13/13 PASS
- drawio native gate: 13/13 PASS
- drawio image-exact gate: 13/13 PASS
- final unittest: 39 tests PASS

## Authority rule

JSONL records are the intended source of authority.
Generated SVG / drawio / HTML artifacts are reproducible outputs, not the authority.

## CI status

CI is intentionally not installed yet.
The next step is to add a workflow that runs the compiler, validates SVG/drawio artifacts, and uploads a directly viewable embedded HTML gallery.
