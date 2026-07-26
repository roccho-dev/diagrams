# Destructive cases

The local preflight executes or fixes the failure oracle for 20 cases.

| ID | Destructive case | Local result |
|---|---|---:|
| D01 | semantic metadata omitted | PASS |
| D02 | independent state artifact renamed and reintroduced | PASS |
| D03 | unknown or misplaced event field | PASS |
| D04 | cross-namespace ID collision makes an edge endpoint ambiguous | PASS |
| D05 | invalid command appends before validation | PASS |
| D06 | visual edit contaminates semantic hash | PASS |
| D07 | semantic edit contaminates visual hash | PASS |
| D08 | Venn members / ERD columns disappear | PASS |
| D09 | projection reads a hidden state file | PASS |
| D10 | ancestors are reported as unrelated obstacles | PASS |
| D11 | real draw.io save strips user objects | NOT PROVEN |
| D12 | raw editor diff cannot become one valid event | NOT PROVEN |
| D13 | exact canonical fixture parity fails after deletion | NOT PROVEN |
| D14 | revised-head locked ELK/Nix drifts | PARTLY PROVEN |
| D15 | inferred terminal-center route is called exact | PASS |
| D16 | missing/tampered proof evidence still uploads green | PASS |
| D17 | proof reducer remains after cutover | PASS contract; cutover NOT RUN |
| D18 | CI green is mistaken for accepted architecture decision | PASS boundary |
| D19 | concurrently written log invalidates manifest after success | PASS |
| D20 | private self-roundtrip URL is mistaken for diagrams.net format | PASS payload; origin render NOT PROVEN |

Local PASS means the corrected local source has an executable failure oracle. It does not promote D11-D14 or canonical cutover to PASS.
