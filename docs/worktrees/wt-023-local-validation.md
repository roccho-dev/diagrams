# wt-023 local validation

Validated locally before opening PR:

```text
python -m unittest discover -s tests -v
```

Result:

```text
Ran 15 tests in 2.464s
OK
```

Semantic roundtrip PoC command:

```text
python tools/build_semantic_roundtrip_poc.py --out /mnt/data/semantic-roundtrip-test
```

Result:

```json
{
  "schema": "SemanticRoundtripPocReport.v1",
  "status": "PASS",
  "fixtures": [
    {"fixture": "lane-progress-triptych", "accepted": true},
    {"fixture": "graph-roundtrip", "accepted": true},
    {"fixture": "visual-patch-isolation", "accepted": true},
    {"fixture": "table-region-boundary", "accepted": true}
  ]
}
```

This validation is evidence only. CI remains the merge gate.
