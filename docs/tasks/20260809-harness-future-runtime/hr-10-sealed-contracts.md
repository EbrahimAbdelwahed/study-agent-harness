# Task Bead: hr-10-sealed-contracts Sealed verification contracts and leak oracle

Status: Open
Priority: P1
Type: task
Depends On: hr-01-contract-firewall, hr-02-job-store, hr-04-decision-trace
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

Harness provides portable sealed verification refs, novelty, learner-safe views, and opaque presentation grants; a complete leak oracle blocks question/answer exposure before generation.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- HR-10 refs/pins, novelty, safe views, PresentationGrant, injected validation, idempotent commands, and leak oracle.
- README application-level sealing and no sealed content in generic paths.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-10-sealed-contracts.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Closed serialization, authority, and leak fixtures fit one fresh Luna xhigh context with security review.

## Context

HR-10 consumes PF-05 SourceRevisionRef and HR-01 authority without web imports; sealing is application authority, not encryption.

## What To Do

- Add verification contracts/store/views/novelty and presentation grant/port.
- Implement threshold vectors, grant binding, and idempotent commands.
- Scan nested generic paths and unknown kinds for sealed markers, identity, secrets, questions, and answers.

## Likely Files / Packages

- src/study_agent/verification/contracts.py
- src/study_agent/verification/store.py
- src/study_agent/verification/views.py
- src/study_agent/verification/novelty.py
- src/study_agent/verification/presentation.py
- src/study_agent/ports/presentation_authority.py
- tests/unit/verification/test_contracts.py
- tests/unit/verification/test_novelty.py
- tests/contract/verification/test_serialization.py
- tests/contract/verification/test_presentation_grants.py
- tests/adversarial/test_sealed_content_leaks.py

## Acceptance Criteria

- [ ] Schemas, pins, thresholds, safe views, and grant commands round-trip deterministically; changed idempotency bytes fail closed.
- [ ] Grant validation binds revision/attempt/scope/cursor/expiry before sealed reads and raw answer text stays host-resolved.
- [ ] Focused leak test plus separate semantic/security reviews pass; generation remains unavailable.

## Verification

- `.venv/bin/python -m pytest tests/unit/verification/test_contracts.py tests/unit/verification/test_novelty.py tests/contract/verification/test_serialization.py tests/contract/verification/test_presentation_grants.py tests/adversarial/test_sealed_content_leaks.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/verification src/study_agent/ports/presentation_authority.py tests/unit/verification tests/contract/verification tests/adversarial/test_sealed_content_leaks.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- Web modules, generators, Cardine approval, attempts/grades/contests, encryption claims, and paths outside the allowlist.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
