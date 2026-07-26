# Post-gate decision overlay

Parent architecture issue: `roccho-dev/adrs#257`.
Approval receipt architecture dependency: `roccho-dev/adrs#260`.
Provider-neutral verifier dependency: `roccho-dev/governance#182`.
Provider evidence adapter dependency: `roccho-dev/ops#89`.

## Boundary

```text
semantic draw.io
  -> geometry facts and findings
  -> policy + exact waiver
  + previously VALID approvalReceipt.v1
  -> receipt-only gate
  -> post-gate review projection
```

The semantic diagram is the only diagram accepted by the checker. The review diagram is a generated, non-authority projection and is rejected by semantic quality/roundtrip entries.

Diagrams does not call a provider API, validate authority grants, map a login to a person/role, or reinterpret provider evidence. It consumes only exact receipt bytes, reference and digest.

## Status axes

```text
verification = COMPLETE | PARTIAL | ERROR
gateStatus   = VALID | ERROR
decision     = ALLOW | REVIEW | DENY
risk         = CLEAN | OPEN | ACCEPTED
```

A waiver changes only a finding disposition. It cannot delete facts/findings, make `PARTIAL` become `COMPLETE`, waive integrity failures, or convert an INVALID/ERROR/mismatched receipt into accepted risk.

## Waiver contract

```json
{
  "schema": "DiagramWaiver.v1",
  "approvalReceiptRef": "approval:...",
  "approvalReceiptDigest": "sha256:..."
}
```

The old free-form `approvalRef` field is rejected. No dual path exists.

The receipt must bind the exact repository, candidate revision, finding digest, policy digest, accepted action, authority scope, provider evidence digest, engine digest and explicit evaluation time. Any missing or mismatched value produces `gateStatus=ERROR`, `decision=DENY`, `risk=OPEN`.

## Run

```sh
jsonl-diagram-core materialize-review \
  examples/post_gate_overlay/semantic.drawio \
  --policy examples/post_gate_overlay/policy.json \
  --waivers examples/post_gate_overlay/waivers.jsonl \
  --approval-receipts examples/post_gate_overlay/approval-receipts.jsonl \
  --repository roccho-dev/diagrams \
  --candidate-revision aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
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

`diagram.review.drawio` stores generated badges on a dedicated draw.io layer using XML user objects. Accepted badges retain `approvalReceiptRef` and `approvalReceiptDigest`; fixed draw.io save must preserve both. Badge text has no authority.

## Claim ceiling

```text
validApprovalReceiptRequired=true
freeFormApprovalRefRetired=true
providerEvidenceValidatedByDiagrams=false
physicalHumanIdentityProven=false
accountNonCompromiseProven=false
allRepositoriesEnforced=false
businessOutcomeAchieved=false
corporateSaleOutcomeAchieved=false
```

The model-exact checker covers axis-aligned rectangles and center-to-center edge approximation. Approximate routes keep `verification=PARTIAL`. Text layout, rotation, z-order, font, opacity, and final draw.io rendering remain separate render-audit responsibilities.
