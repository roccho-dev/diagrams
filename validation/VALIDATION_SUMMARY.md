# Validation summary

| Gate | Result |
|---|---|
| Python unittest discovery | PASS, 12 tests |
| `npm ci --no-audit --no-fund --ignore-scripts` | PASS, 2 packages |
| `build_suite.py --require-engines` | PASS; 08/10 use ELK, 09 uses Graphviz without fallback |
| Legacy semantic compare | PASS, 12 legacy samples across events + DVM layers |
| SVG provenance/proof | PASS, 13 SVG |
| D2/ELK semantic smoke | PASS; structural compiled-D2 parity for 13 samples + ELK runtime smoke |
| Rebuild compare with required engines and smoke | PASS, 94 files compared, no changed/missing/extra/proof errors |
| Wheel build | PASS, `jsonl_diagram_core-0.1.0-py3-none-any.whl` |
| Core/adapters source boundary | PASS, no adapter imports from `src` |
| HTML source check | PASS, 0 HTML files |
| JSON/JSONL parse excluding dependency/cache artifacts | PASS, 61 JSON + 43 JSONL |
| Nix | NOT RUN locally: `nix` binary absent; required in external CI |

The semantic gate treats generated SVG/D2/layout/proof as non-authority evidence. The authoritative comparison is against `events.jsonl`; DVM is also compared to catch reducer-level semantic loss.
