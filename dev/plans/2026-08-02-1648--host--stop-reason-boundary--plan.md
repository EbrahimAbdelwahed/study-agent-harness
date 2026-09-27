# Plan: Stop reason boundary

Date: 2026-08-02 16:48 CEST
Area: host

## Goal

Remove the ambiguous learner-input reason from the shared `StopDecision`
contract while preserving `AskLearnerDecision` as the only learner-question
path and retaining the two unambiguous stop outcomes.

## Scope

- In scope: stop enum, generated decision schema, strict decoder behavior, and
  focused ask/stop runner contracts.
- Out of scope: changing runner result statuses, tool operations, downstream
  chat schemas, or any external product repository.

## Approach

1. Remove only the legacy enum member; schema generation will then advertise
   exactly `completed` and `no_safe_action`.
2. Pin rejection of the legacy serialized value and round trips for both
   supported stop reasons.
3. Pin runner outcomes for ask, completed stop, and no-safe-action stop.

## Risks

- The same text remains a valid runner status for `AskLearnerDecision`; it must
  not be removed from `TutorHostRunStatus`.

## Verification

- Host contract and runner unit modules
- Ruff and mypy on the touched host files
- Repository occurrence and diff audits
