# Task Bead: TUT-03B1 playbook inspection and cancellation

Status: Ready
Priority: P0
Type: tracer-bullet
Depends On: TUT-03A

## Outcome

The existing engine can validate and inspect every persisted checkpoint without
effects, and distinguishes transport-confirmed cancellation from failure.

## Acceptance Criteria

- [ ] `inspect` validates canonical bytes, definition, inputs, pins, and read
  dependencies for running, suspended, completed, failed, and cancelled runs.
- [ ] Inspection exposes checkpoint and definition fingerprints, next-step and
  suspended-dialogue identity, but never returns `VerifiedRunRecord`.
- [ ] `recover` remains restricted to completed or deterministically terminated
  successful runs.
- [ ] `ModelErrorCode.CANCELLED` and `ModelFinishReason.CANCELLED` atomically
  persist cancelled checkpoint/trace/result state.
- [ ] Generic exceptions remain failed; `asyncio.CancelledError` and process
  interruption propagate and are never relabelled cancelled.
- [ ] Corrupt/tampered observed runs fail closed and inspection performs no tool
  or model effect.

## Verification

- Engine value/codec/inspection/cancellation unit tests, dialogue integration,
  existing recovery/CAS tests, full offline gates.
