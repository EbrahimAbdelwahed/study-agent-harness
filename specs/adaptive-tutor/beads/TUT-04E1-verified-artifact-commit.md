# Task Bead: TUT-04E1 verified generated-batch commit

Status: Blocked on TUT-04B and TUT-04C1
Priority: P0
Type: expand
Depends On: TUT-04B, TUT-04C1

## Outcome

The artifact service proof port is backed by persisted verified capability runs,
so generated content/provenance cannot be caller-forged.

## Acceptance Criteria

- [ ] Adapter retrieves the completed verified run and reconstructs batch,
  profile selection, pins, prompt/model/validator receipts, dependencies, output
  fingerprint, and canonical source commitments.
- [ ] Temporary candidate keys resolve to deterministic artifact/revision IDs
  and parent links before one proposal-batch append.
- [ ] Failed, suspended, terminated, cancelled, stale, tampered, or mismatched
  runs cannot append; exact retry does not repeat model/search or event effects.

## Verification

- Verified-run/process-loss/idempotency/tamper/source-drift integration and full
  gates.
