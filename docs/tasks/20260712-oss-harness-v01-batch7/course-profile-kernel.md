# Task Bead: course-profile-kernel Implement immutable canonical course profiles

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260712-oss-harness-v01-batch7`
Spec: `docs/specs/oss-harness-v0-1-typed-tools-and-reference-harness.md`

## Worker Profile

create `course-state-worker`

Rationale:

No reusable specialization selected yet.

## Context

course.get and all downstream writes require a real event-sourced course aggregate.

## What To Do

- Implement exact course.created@1 codec/reducer and deterministic idempotent CourseService.create.
- Add projection-only CourseViewPort and structured manifest codec.
- Require canonical course existence before text ingestion and session start.
- Migrate fixtures and prove mixed replay.

## Likely Files / Packages

- domain/course.py and course exports
- new courses/events.py, projection.py, service.py, view.py
- ports/course.py
- ingestion/service.py and sessions/service.py guards
- course unit/contract/integration tests

## Acceptance Criteria

- [ ] Same profile is idempotent; changed profile conflicts.
- [ ] Envelope/profile/course identity and exact payload are strict.
- [ ] Orphan ingestion/session start fails before blobs/events.
- [ ] Mixed replay remains byte-identical.

## Verification

- `.venv/bin/python -m pytest tests/unit/courses tests/contract/course tests/integration/test_course_profile_kernel.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output

## Out Of Scope

- Course update/delete, CLI, public tools, providers, product.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
