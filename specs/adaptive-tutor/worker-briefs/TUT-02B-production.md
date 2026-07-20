# Worker Brief: TUT-02B production

## Goal

Implement `TutorSnapshotV1` as one deterministic, sequence-consistent host read
over the already-canonical course stream.

## Allowed Files

- `src/study_agent/domain/tutor_snapshot.py`
- `src/study_agent/domain/__init__.py` for public exports only
- `src/study_agent/ports/tutor_snapshot.py`
- `src/study_agent/ports/__init__.py` for public exports only
- `src/study_agent/tutor_snapshot/__init__.py`
- `src/study_agent/tutor_snapshot/reader.py`
- `src/study_agent/cli/repository.py` for composition only

## Forbidden Files

- Tests, events, reducers, existing projection shapes, source/session/context
  command services, lifecycle, export schemas, capabilities, skills, playbooks,
  prompts, model adapters, UI, docs/specs, and `sbobby-web`.

## Fixed Contract

- `TutorSnapshotReader.get(course_id, session_id)` captures
  `tuple(EventStore.read(course_id))` once and calls `replay(...)` once.
- Existing projection views are rebound to that captured projection; no live
  view or store read may occur during composition.
- Snapshot schema version is exactly 1 and serializes deterministically.
- Snapshot contains course/session identity, high-water sequence, a bounded
  session summary, separately attributed configured hints, all five learner
  context fields, exact configured/learner divergences, one course-sequence
  ordered session timeline, notes, and current material summaries.
- Learner-context states are `missing`, `known`, or `conflicting`. Additive
  kinds with multiple active declarations remain known; only canonical scalar
  conflicts are conflicting.
- Configured hints map only `learning_goals -> objective`,
  `assessment_styles -> assessment_format`, and `exam_date -> deadline`.
  Divergence is exact canonical inequality when both configured and active
  learner values exist; neither source wins.
- Timeline includes HUMAN and NOTE interaction events, grounded assistant
  answer events, and general assistant-turn events. Each entry retains event ID
  and course sequence; assistant entries retain run/status and reply linkage.
- Material summaries expose only the captured projection's
  `current_revision_id` for each source and strictly validate source ownership.
- No capability, next-action, recommendation, provider, hypothesis, learner
  style, or mastery field exists.

## Verification

- Ruff and strict mypy over changed source files.
- Existing course/session/context/source and architecture tests.
- `git diff --check`.
