# Worker Profile: tutor-snapshot-worker

## Mission

Build deterministic, read-only tutor snapshots from one immutable capture of a
course event stream. The worker composes existing canonical projections; it does
not invent tutor policy or write canonical state.

## Model And Effort

- Model family: Luna
- Reasoning effort: xhigh
- Recursive delegation: forbidden

## Boundaries

- May add typed snapshot values, a read port, a snapshot reader, public exports,
  and local repository composition.
- Must use exactly one `EventStore.read(course_id)` and exactly one replay per
  snapshot request.
- Must reuse projection-bound course, session, study-context, and assistant-turn
  validation rather than query independently live views.
- Must not add events, reducers, capabilities, next-action recommendations,
  hypotheses, mastery, provider calls, prompts, skills, playbooks, UI, or
  `sbobby-web` changes.
- Must not change the existing seven StudyTools or existing event schemas.

## Quality Gates

- Old and mixed streams replay deterministically.
- Timeline ordering is course-sequence ordering and every turn names event
  evidence.
- Configured hints and learner statements retain separate attribution.
- Current material summaries are selected only from the captured projection.
- Ruff, strict mypy, focused tests, full offline pytest, and diff check pass.
