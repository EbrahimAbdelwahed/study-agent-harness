# Task Bead: TUT-03C1 validator-gated optional dialogue

Status: Ready
Priority: P0
Type: tracer-bullet
Depends On: TUT-03B

## Outcome

A linear playbook can skip or suspend one dialogue from a deterministic prior
validator result without adding a general branch graph.

## Acceptance Criteria

- [ ] `DialogueGate` immutably binds a prior validator boolean and typed default
  response; invalid or forward/model/run-input references are rejected.
- [ ] False writes the default, a fail-closed skipped receipt, and continues
  without returning suspended; true preserves existing CAS suspension/resume.
- [ ] Definition fingerprints bind the gate and default response.
- [ ] Inspection/recovery recomputes the gate and rejects condition, receipt,
  default-output, trace-shape, and payload tampering.
- [ ] Existing unconditional dialogue bytes/behavior and old resumed receipts
  remain compatible.
- [ ] No new outcome, store, planner, provider, tool, or canonical state owner.

## Verification

- Contract/value, direct/skip/resume/tamper/legacy integration, architecture,
  and full offline gates.
