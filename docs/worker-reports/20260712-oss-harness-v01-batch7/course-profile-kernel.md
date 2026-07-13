# Worker Report: course-profile-kernel

Status: complete
Run ID: `20260712-oss-harness-v01-batch7`
Task: `docs/tasks/20260712-oss-harness-v01-batch7/course-profile-kernel.md`
Brief: `docs/worker-briefs/20260712-oss-harness-v01-batch7/course-profile-kernel.md`
Agent: course_profile_kernel_impl
Reported: 2026-07-12 03:14

## Files Changed

- courses event/projection/service/view and ports/course: immutable canonical CourseProfile aggregate
- ingestion/service.py and sessions/service.py: mandatory course-existence guard before effects
- course tests and migrated course-first fixtures: exact codec/idempotency/orphan/mixed replay coverage

## Behavior Implemented

- course.created@1 is the only course mutation and produces additive event-sourced projection state.
- Orphan source ingestion and session start fail before blob/event writes.

## Verification

- .venv/bin/python -m pytest: 239 passed, 1 expected skipped
- .venv/bin/python -m ruff check .: passed
- .venv/bin/python -m mypy: passed across 120 source files

## Open Questions Or Blockers

- None.

## Follow-up Beads Needed

- Build GroundingAskService only after independent course-kernel approval.
