# Worker Brief: TUT-05A production

## Goal

Implement the provider-neutral canonical assessment values, strict event codecs,
pure reducers, and projection-only views defined by TUT-05A. Do not implement
commands or grading behavior.

## Worker Profile

Use `assessment-evidence-worker`. Keep this worker limited to inward contracts,
event/reducer ownership, and narrow composition registration.

## Allowed Files

- `src/study_agent/domain/identifiers.py`
- `src/study_agent/domain/assessment.py`
- `src/study_agent/domain/__init__.py`
- `src/study_agent/assessments/__init__.py`
- `src/study_agent/assessments/contracts.py`
- `src/study_agent/assessments/events.py`
- `src/study_agent/assessments/projection.py`
- `src/study_agent/assessments/view.py`
- `src/study_agent/ports/assessment.py`
- `src/study_agent/ports/__init__.py`
- `src/study_agent/cli/repository.py`
- `src/study_agent/application/export.py`
- `src/study_agent/adapters/sqlite/lifecycle_observer.py`

## Forbidden Files

- Tests, prompts, skills, playbooks, capabilities, tools, model/gateway/worker
  adapters, service or grading modules, artifact content/provenance schemas,
  tutor snapshots, recall/scheduling, dependencies, ADRs/specs, `sbobby-web`,
  and the seven StudyTools.

## Required Context

- ADR-0004, TUT-05, and TUT-05A.
- Existing artifact lifecycle contracts/events/projection/view and session event
  codec/CAS patterns.
- `AssessmentItemContent` is immutable artifact content with format, prompt,
  options, expected response, and evaluation criteria. Do not duplicate or
  mutate it in the assessment owner.

## Required Contracts

- Add typed `PresentationId`, `AttemptId`, and `GradeId` plus deterministic
  derivation functions. Trusted course/session/retry or target identities are
  inputs; timestamps, responses not owned by the command, and model-proposed
  keys are not.
- Define inward closed vocabularies and frozen records for canonical response,
  grade status, criterion result, grade lifecycle, grade provenance, contest,
  complete assessment snapshot, and learner-redacted presentation view.
- Define exact schema-v1 codecs for:
  - `assessment.item_presented`: accepted artifact revision id, exact
    `sha256(content_bytes)`, redacted format/prompt/options snapshot,
    idempotency key, and command fingerprint;
  - `assessment.attempt_recorded`: presentation id, closed response union,
    response fingerprint, optional non-negative latency, key/fingerprint;
  - `assessment.grade_recorded`: attempt id, strict outcome and criterion
    results, optional superseded grade id, deterministic-or-verified provenance,
    key/fingerprint;
  - `assessment.grade_contested`: grade id, trimmed bounded reason,
    key/fingerprint.
- Grade provenance is a strict union. Deterministic provenance has policy
  id/version/fingerprint and rubric fingerprint with no model fields. Verified
  provenance has sanitized run/capability/definition/proof, prompt/model/
  validator receipts and rubric fingerprint. Reject provider selectors,
  credentials, secret-shaped data, raw traces, and failed validators.
- The reducer validates presentation references against the already-replayed
  `study_artifacts` state: exact course, accepted status, assessment kind,
  immutable content fingerprint, and exact redacted snapshot. Expected response
  and evaluation criteria stay internal and never enter the learner view.
- Pin closed encoding at presentation/replay: `SINGLE_CHOICE.expected_response`
  is exactly one listed option; `MULTIPLE_CHOICE.expected_response` is a
  canonical JSON array string containing unique listed options; stored learner
  selection order follows artifact option order. Free response is trimmed text.
- Enforce event order and authority in reducers: SERVICE presentation, HUMAN
  attempt, SERVICE grade, HUMAN contest; attempt needs presentation, grade needs
  attempt, contest needs grade, and supersession needs the exact same-attempt
  active predecessor. Preserve all prior records.
- Store one bounded `assessments` projection section with presentations,
  attempts, grades, contests, and command receipts. Validate all existing state
  before each reduction and expose deterministic typed views.
- Register assessment events after artifact events in canonical CLI repository,
  export replay, and lifecycle observer composition. Registration is additive
  and must not alter existing event/tool/capability fingerprints.

## Acceptance Criteria

- Exact codecs reject unknown/extra fields, malformed unions/fingerprints,
  wrong authority, impossible order, cross-owner references, duplicates,
  mastery/scheduling/learner-model fields, and secret-shaped data.
- Projection replay is pure and byte-identical; views cannot expose hidden
  answer or rubric material to learners.
- Inward assessment modules do not import adapters, CLI, capability, gateway,
  model, prompt, playbook, skill, tool, UI, provider SDK, or `sbobby-web` code.
- This bead defines no service, policy implementation, model execution, or
  canonical command method.

## Verification

- `.venv/bin/ruff check src`
- `MYPYPATH=src .venv/bin/mypy --strict src`
- Existing artifact, session, event-store, export, architecture, and public
  seven-tool contract tests.
- `git diff --check`

## Report

Report public names, event payloads, projection shape, composition changes,
commands/results, and any conflict with TUT-05A. Do not commit or delegate.
