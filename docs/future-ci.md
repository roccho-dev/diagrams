# Future CI plan

CI is intentionally deferred for the initial main baseline.

Required future gate:

1. Install project dependencies.
2. Run JSONL compiler against canonical samples.
3. Generate SVG artifacts.
4. Generate native drawio artifacts.
5. Generate image-exact drawio artifacts.
6. Validate SVG XML parse and semantic counts.
7. Validate drawio XML root/layer/id/source/target structure.
8. Build an embedded no-websandbox HTML gallery.
9. Upload SVG, drawio, reports, and gallery as GitHub Actions artifacts.

Definition of done:

- CI fails on invalid JSONL, invalid SVG, invalid drawio, missing gallery, or missing provenance.
- CI artifact contains `index.html` that can be opened immediately after a run.
