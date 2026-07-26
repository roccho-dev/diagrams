# Post-gate decision overlay

Parent architecture issue: `roccho-dev/adrs#257`.

## Boundary

```text
semantic draw.io
  -> geometry facts and findings
  -> policy + exact waiver gate
  -> post-gate review projection
```

The semantic diagram is the only diagram accepted by the checker. The review diagram is a generated, non-authority projection and is rejected by semantic quality/roundtrip entries.

## Status axes

```text
verification = COMPLETE | PARTIAL | ERROR
gateStatus   = VALID | ERROR
decision     = ALLOW | REVIEW | DENY
risk         = CLEAN | OPEN | ACCEPTED
```

A waiver changes only a finding disposition. It cannot delete facts/findings, make `PARTIAL` become `COMPLETE`, or waive integrity failures.

## Run

```sh
jsonl-diagram-core materialize-review \
  examples/post_gate_overlay/semantic.drawio \
  --policy examples/post_gate_overlay/policy.json \
  --waivers examples/post_gate_overlay/waivers.jsonl \
  --as-of 2026-07-26T12:00:00+09:00 \
  --out-dir /tmp/post-gate-overlay
```

Outputs:

```text
diagram.semantic.drawio
diagram.geometry.json
diagram.gate.json
diagram.gate-receipt.json
diagram.review.drawio
diagram.projection-receipt.json
```

`diagram.review.drawio` stores generated badges on a dedicated draw.io layer using XML user objects. Badge text has no authority; accepted status comes only from the validated waiver record.

## Claim ceiling

The model-exact checker covers axis-aligned rectangles and center-to-center edge approximation. Approximate routes keep `verification=PARTIAL`. Text layout, rotation, z-order, font, opacity, and final draw.io rendering remain outside this PR.
