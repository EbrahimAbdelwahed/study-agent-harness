# Worker Brief: TUT-02A production

## Goal

Implement the fixed conversation-turn contract in TUT-02A without changing old
session event payloads or projection bytes.

## Allowed Files

- `src/study_agent/domain/identifiers.py`
- `src/study_agent/domain/session.py`
- `src/study_agent/domain/__init__.py`
- `src/study_agent/sessions/events.py`
- `src/study_agent/sessions/projection.py`
- `src/study_agent/sessions/turns.py`
- `src/study_agent/sessions/turn_service.py`
- `src/study_agent/sessions/turn_view.py`
- `src/study_agent/sessions/__init__.py`
- `src/study_agent/ports/session.py`
- `src/study_agent/ports/__init__.py`
- `src/study_agent/cli/repository.py` for composition only
- `src/study_agent/application/export.py` for strict allowlisting only

## Forbidden Files

- Tests, old event payload shapes, old reducers' output manifests,
  ContinuationSummaryV1, skills/playbooks/prompts/tools/model adapters, docs/specs,
  and `sbobby-web`.

## Fixed Invariants

- `tutor_message@1` content/status/reply linkage comes from VerifiedRunRecord.
- General assistant messages live in an additive projection key absent from old
  streams.
- Learner events remain HUMAN-kind existing session events.
- All authority, retry, CAS, run uniqueness, and relational replay rules in
  TUT-02A are mandatory.

## Verification

- Ruff changed production files, strict mypy src, existing session/export/
  lifecycle tests, old-projection byte check, diff check.
