# Log: recall and capability-gap status reconciliation

Date: 2026-07-24 19:10
Area: adaptive tutor / capability-gap feedback

## Summary

Reconciled bead status with the integrated, reviewed implementation. TUT-07A,
TUT-07B, and TUT-07C are complete; TUT-07D remains the recall closure bead.
GAP-01, GAP-02, GAP-03, GAP-04A, and GAP-05A are complete after the aggregated
security review and approved hardening passes.

## Verification

- Full offline suite: 1750 passed, 10 opt-in/optional skips.
- Strict mypy: 457 source files passed.
- Ruff: passed.
- Security review findings for outbox concurrency/redaction, trusted source
  evidence, and workaround approval/execution were fixed and regression-tested.
- Recall review findings for identity binding, longitudinal sessions,
  single-high-water reads, strict projection shapes, retry policy drift, and
  optional FSRS CI were fixed and regression-tested.

## Remaining

- TUT-07D replay/composition/export closure.
- TUT-08 configured GPT host and submission gates.
- GAP-05B must be implemented in a separately versioned private devkit; the
  existing directory is currently untracked inside the dirty `sbobby` parent.
