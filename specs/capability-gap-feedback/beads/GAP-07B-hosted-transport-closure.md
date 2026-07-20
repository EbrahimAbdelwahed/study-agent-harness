# Task Bead: GAP-07B hosted transport-to-import closure

Status: Scope approved — blocked on GAP-05B, GAP-05D and adapter selection
Priority: P1
Type: contract
Depends On: GAP-05B, GAP-05D

## Outcome

A private factory worker consumes durable hosted inbox records through the typed
port, invokes the GAP-05B importer, and acknowledges only the correct delivery
without making hosted infrastructure mandatory for the local OSS loop.

## Slice Strategy

contract

Fresh Context Fit: yes

## Spec Coverage

- Production path from hosted tutor delivery to normal private Flywheel intake.

## Grilling Evidence

- Session/artifact: accepted ADR-0011 transport amendment and GAP-05B/D reports.
- Decision state: scope approved 2026-07-18; dependencies and concrete deployment
  adapter selection remain.
- ADR/glossary changes: none expected.

## Worker Profile

reuse `test-engineer`, `security-reviewer`, and `reviewer`

## Acceptance Criteria

- [ ] Factory consumption validates the exact durable bytes before invoking the
  importer and acknowledges only after importer persistence succeeds.
- [ ] Retry/process loss makes each trusted `delivery_import_id` contribute at
  most once. Identical bundles from different sender scopes have distinct
  delivery IDs but converge into the same candidate/aggregate only through the
  normal GapKey rules.
- [ ] Sender scope authenticates/deduplicates delivery and the derived delivery
  ID controls import idempotency, but neither reaches Flywheel proposal evidence.
- [ ] Intake downtime or factory failure leaves the delivery pending and study
  remains usable.
- [ ] Tutor runtime cannot address Flywheel commands, repositories, proposals,
  decisions, or implementation goals.
- [ ] Local GAP-07 closure remains green without hosted infrastructure.

## Verification

- Scripted transport→inbox→factory→import chain, wrong-sender replay, duplicate,
  crash at each acknowledgement boundary, quarantine, privacy, and offline local
  non-regression.

## Out Of Scope

- GitHub synchronization, public endpoint, converter, or feature implementation.
