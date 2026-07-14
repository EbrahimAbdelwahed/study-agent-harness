# Task Bead: TUT-03B1 playbook inspection and cancellation

Status: Done
Priority: P0
Type: tracer-bullet
Depends On: TUT-03A

## Outcome

The existing engine can validate and inspect every persisted checkpoint without
effects, and distinguishes transport-confirmed cancellation from failure.

## Acceptance Criteria

- [x] `inspect` validates canonical bytes, definition, and checkpoint shape for
  running, suspended, completed, failed, and cancelled runs, then exposes the
  exact persisted inputs, pins, and read dependencies for trusted comparison.
- [x] Inspection exposes checkpoint and definition fingerprints, next-step and
  suspended-dialogue identity, but never returns `VerifiedRunRecord`.
- [x] `recover` remains restricted to completed or deterministically terminated
  successful runs.
- [x] `ModelErrorCode.CANCELLED` and `ModelFinishReason.CANCELLED` atomically
  persist cancelled checkpoint/trace/result state.
- [x] Generic exceptions remain failed; `asyncio.CancelledError` and process
  interruption propagate and are never relabelled cancelled.
- [x] Corrupt/tampered observed runs fail closed and inspection performs no tool
  or model effect.

## Verification

- Engine value/codec/inspection/cancellation unit tests, dialogue integration,
  existing recovery/CAS tests, full offline gates.
