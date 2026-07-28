# Compiled official GraphViewer

```text
one exact mxfile
+ pinned jgraph/drawio viewer-static.min.js
+ visibility-only extension
-> self-hostable static bundle
```

The official `GraphViewer` renders shapes, labels, edges, pages, layers, links, pan, zoom and fit. The local extension only evaluates `minScreenWidthPx` and `minScreenHeightPx` against native geometry and current zoom. It does not mutate source XML, reconnect edges, restyle cells, aggregate edges, or introduce a world/LOD IR.

The compiler rejects external source assets, mutable `latest` runtime identities, missing/duplicate stable IDs, malformed pages and invalid thresholds. The generated bundle includes the exact official runtime bytes and license. Runtime CSP uses `connect-src 'none'`.
