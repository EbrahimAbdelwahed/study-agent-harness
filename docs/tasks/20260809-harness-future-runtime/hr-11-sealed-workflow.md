# Task Bead: hr-11-sealed-workflow Sealed generation coverage review and presentation

Status: Open
Priority: P1
Type: task
Depends On: hr-03-executor-recovery, hr-04-decision-trace, hr-05-lifecycle-convergence, hr-10-sealed-contracts
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

Approved profile and accepted plan run through generation Jobs, independent coverage review, deterministic release, targeted regeneration, and progressive presentation; only a portable receipt leaves Harness and HR-12 owns final 1.4.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- HR-11 workflow Job graph, independent reviewer, release predicates, drift/regeneration, pins, presentation, and authority tests.
- README sealed lifecycle, complete coverage, no unsupported claims, historical attempts, and final release ownership.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-11-sealed-workflow.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Workflow, independent reviewer, and sealed security fixtures fit one fresh Luna xhigh context.

## Context

HR-11 is the only generator workflow; it has no web dependency and keeps generator, reviewer, release, and presentation authority separate.

## What To Do

- Add workflow, independent CoverageReviewer, deterministic release, stale regeneration, and presentation service.
- Require approved profile plus accepted plan, complete coverage, zero unsupported claims, version pins, and historical attempts.
- Exercise HR-10 grant validation and leak scans; keep HR-12 as sole 1.4 publisher.

## Likely Files / Packages

- src/study_agent/verification/workflow.py
- src/study_agent/verification/reviewer.py
- src/study_agent/verification/release.py
- src/study_agent/verification/presentation.py
- tests/integration/test_synthetic_verification_workflow.py
- tests/integration/test_verification_targeted_regeneration.py
- tests/integration/test_verification_presentation_receipt.py
- tests/adversarial/test_verification_authority.py
- tests/adversarial/test_sealed_content_leaks.py

## Acceptance Criteria

- [ ] Approved profile/accepted plan, independent review, complete coverage, zero unsupported claims, and deterministic release gate all hold; missing/partial/uncertain blocks.
- [ ] Novelty/drift regeneration is targeted, two failures suspend, prior attempts remain historical, and version pins are complete.
- [ ] Separate focused test, reviewer, and security gates pass; no publication occurs in HR-11 and HR-12 remains sole 1.4 publisher.

## Verification

- `.venv/bin/python -m pytest tests/integration/test_synthetic_verification_workflow.py tests/integration/test_verification_targeted_regeneration.py tests/integration/test_verification_presentation_receipt.py tests/adversarial/test_verification_authority.py tests/adversarial/test_sealed_content_leaks.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/verification tests/integration/test_synthetic_verification_workflow.py tests/integration/test_verification_targeted_regeneration.py tests/integration/test_verification_presentation_receipt.py tests/adversarial/test_verification_authority.py tests/adversarial/test_sealed_content_leaks.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- Self-review/release, automatic academic approval, learner model, pre-attempt questions, prior-attempt mutation, web connectors, Cardine attempts/grades/contests, and paths outside the allowlist.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
