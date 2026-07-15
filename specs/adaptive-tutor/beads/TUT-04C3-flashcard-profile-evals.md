# Task Bead: TUT-04C3 profile gateway and adversarial evals

Status: Blocked on TUT-04C1 and TUT-04C2
Priority: P0
Type: contract
Depends On: TUT-04C1, TUT-04C2

## Outcome

Both profile bindings execute through the gateway with truthful recovery and
produce only verified proposal batches.

## Acceptance Criteria

- [ ] Scripted end-to-end direct, retry, interruption, source drift, fallback,
  and injection cases retain prompt/validator/source provenance.
- [ ] Profile selection cannot change under the same retry identity and no
  generated output contains decisions or canonical artifact IDs.
- [ ] Shared seven-tool and existing capability contracts remain unchanged.

## Verification

- Gateway/eval/architecture/full offline gates.
