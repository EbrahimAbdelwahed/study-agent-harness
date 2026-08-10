# Task Bead: HR-11 Sealed generation coverage review and presentation

Status: Open
Priority: P1
Type: task
Depends On: HR-03-executor-recovery, HR-04-decision-trace, HR-05-lifecycle-convergence, HR-10-sealed-contracts

## Outcome

Approved profile and accepted plan run through generation Jobs, independent coverage review, deterministic release, targeted stale-shard regeneration, and progressive presentation. Harness returns only a presentation receipt; Cardine retains attempts, responses, criteria, grades, and contests. HR-12 alone can publish final 1.4.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-11-sealed-workflow.md`: workflow Job graph, independent reviewer, release predicates, drift/regeneration, version pins, presentation commands, and authority tests.
- `specs/future-runtime/README.md`: sealed lifecycle, complete coverage, no unsupported claims, historical attempts, and final release ownership.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-11-sealed-workflow.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

This is a bounded workflow with a separate reviewer and high-risk sealed authority surface. Execute in one fresh Luna xhigh context with an independent security review.

## Context

HR-11 is the only generator workflow. It consumes HR-03/04/05/10, has no web dependency, and must keep generator, reviewer, deterministic release, and host presentation authority separate. Any missing, partial, uncertain, or unsupported coverage blocks release.

## What To Do

- Add `VerificationWorkflow`, independent `CoverageReviewer`, deterministic release gate, stale-shard regeneration, and presentation service under `src/study_agent/verification/`.
- Create generation child Jobs only after approved profile and accepted plan; pin every question to profile, plan, source revisions, scope/objective refs, and version IDs.
- Apply novelty, drift, historical-attempt, complete-coverage, and zero-unsupported-claim predicates; suspend after two failed regenerations without exposing content.
- Exercise grant commands through HR-10 injected authority port and add raw-identity/secret/question/answer scans.

## Likely Files / Packages

- `src/study_agent/verification/workflow.py`: generation/review/release orchestration.
- `src/study_agent/verification/reviewer.py`, `src/study_agent/verification/release.py`: independent reviewer and deterministic gate.
- `src/study_agent/verification/presentation.py`: progressive safe presentation and receipt.
- `tests/integration/test_synthetic_verification_workflow.py`, `tests/integration/test_verification_targeted_regeneration.py`, `tests/integration/test_verification_presentation_receipt.py`: workflow/replay/presentation.
- `tests/adversarial/test_verification_authority.py`, `tests/adversarial/test_sealed_content_leaks.py`: authority and security scans.

## Acceptance Criteria

- [ ] Generation starts only for approved profile plus accepted plan; reviewer is independent, required coverage is complete, unsupported claims are zero, and deterministic release blocks missing/partial/uncertain coverage.
- [ ] Novelty/drift regeneration targets affected shards, creates a new revision, reruns global review, suspends after two failed regenerations, and preserves prior attempts.
- [ ] Presentation commands validate the HR-10 grant tuple before sealed reads; same-key commands converge, changed bytes conflict, and receipts/traces/errors contain no raw identity, secrets, questions, or answers.
- [ ] Focused workflow test gate and independent reviewer gate are separate; an independent security review approves sealed authority/leak evidence; HR-12 remains the sole 1.4/final publisher.

## Verification

- `.venv/bin/python -m pytest tests/integration/test_synthetic_verification_workflow.py tests/integration/test_verification_targeted_regeneration.py tests/integration/test_verification_presentation_receipt.py tests/adversarial/test_verification_authority.py tests/adversarial/test_sealed_content_leaks.py`: focused gates pass.
- `.venv/bin/python -m pytest`: global offline suite and deterministic workflow report pass.
- `.venv/bin/python -m ruff check src/study_agent/verification tests/integration/test_synthetic_verification_workflow.py tests/integration/test_verification_targeted_regeneration.py tests/integration/test_verification_presentation_receipt.py tests/adversarial/test_verification_authority.py tests/adversarial/test_sealed_content_leaks.py`: lint passes.
- `.venv/bin/python -m mypy`: strict typing remains green.
- `git diff --check`: clean.

## Out Of Scope

- Generator self-review/release, automatic academic approval, learner-model computation, exposed pre-attempt questions, prior-attempt mutation, web connectors, Cardine attempt/grade/contest behavior, and edits outside listed paths.

## Invariants

- Independent reviewer and deterministic release gate are distinct from generator output.
- Cardine owns attempt/response/grade/contest; Harness emits a portable presentation receipt.
- HR-12 alone publishes final aggregate release 1.4.

## Stop Conditions

- Stop if any required coverage is absent/uncertain, claims are unsupported, reviewer shares generator state, or sealed content is exposed.
- Stop if a source drift path mutates prior attempts or bypasses global review.

## Review Gate

Focused tests, independent reviewer, and independent security gates are separate prerequisites; no release publication occurs here.

## Notes / Handoff

- HR-12 aggregates HR-11 evidence and runs final package/release gates.
