# Slice 03: Capability gateway

## Outcome

An agent host can discover, start, and resume built-in versioned tutor
capabilities through one model- and runtime-independent interface.

## Contract

- Outcomes are completed, suspended, terminated, cancelled, stale, or failed.
- Continuations bind run, pins, inputs, read dependencies, and authority.
- Initial capabilities are `explain_concept@1` and
  `assess_understanding@1` with offline eval fixtures.
- The exact seven `agent-operations@1` StudyTools remain unchanged.
