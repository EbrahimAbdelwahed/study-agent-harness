# Task Bead: GAP-05C scoped proposal and maintainer decision

Status: Approved — blocked on GAP-05B implementation
Priority: P1
Type: tracer-bullet
Depends On: GAP-05B

## Outcome

Each intake candidate becomes one immutable technical proposal and one unresolved
maintainer decision, scoped to one gap key or explicitly reviewed equivalent
cohort, without starting implementation.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Options, recommendation, draft ADR/spec/beads, visible authorization scope,
  and one decision per coherent feature.

## Grilling Evidence

- Session/artifact: GAP-05B reproduction/duplicate evidence.
- Decision state: scope approved 2026-07-18; implementation dependency remains.
- ADR/glossary changes: draft only until accepted.

## Worker Profile

reuse `feature-spec-architect` and `implementation-orchestrator`; require
`architecture-auditor`

## What To Do

- Generate proposal options/recommendation, draft ADR/spec/beads, verification,
  and explicit non-goals from one candidate's structured evidence.
- Freeze cohort membership and proposal fingerprint before creating the decision.
- Permit cohort consolidation only for exact GapKey duplicates or an explicit
  pre-decision maintainer merge; never infer it from format similarity.
- State exactly whether acceptance authorizes planning only or planning plus an
  implementation goal; merge/release/deploy remain excluded.

## Acceptance Criteria

- [ ] Independent gaps always produce independent proposals/decisions.
- [ ] Decision displays immutable cohort, evidence, reproduction limits, draft
  scope, options, recommendation, and exact authority requested.
- [ ] Retry creates neither a second proposal nor decision.
- [ ] No approved artifact, goal, code, dependency, GitHub issue, network effect,
  or dispatch exists before resolution.

## Verification

- Multi-gap/cohort, duplicate, immutable fingerprint, retry/process-loss, missing
  evidence, and decision-request validation tests.

## Out Of Scope

- Decision resolution, promotion, implementation, or external issue creation.
