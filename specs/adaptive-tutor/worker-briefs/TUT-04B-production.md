# Worker Brief: TUT-04B production

## Goal

Implement the event-sourced proposal, decision, and explicit supersession
lifecycle for canonical study-artifact revisions.

## Allowed Files

- `src/study_agent/domain/artifact.py`
- `src/study_agent/domain/__init__.py`
- `src/study_agent/domain/identifiers.py`
- `src/study_agent/artifacts/__init__.py`
- `src/study_agent/artifacts/contracts.py`
- `src/study_agent/artifacts/events.py`
- `src/study_agent/artifacts/projection.py`
- `src/study_agent/artifacts/service.py`
- `src/study_agent/artifacts/view.py`
- `src/study_agent/ports/artifact.py`
- `src/study_agent/ports/__init__.py`

## Forbidden Files

- Tests, docs/specs, capabilities, skills, playbooks, prompts, adapters,
  composition roots, CLI/export, other state owners, dependencies,
  repository configuration, and `sbobby-web`.

## Required Context

- ADR-0002, ADR-0008, ADR-0009, TUT-04B, and TUT-04A contracts.
- Existing study-context and session event/projection/service/view conventions.
- Canonical per-course event stream, exact retry, CAS, and replay rules.

## Public Shape

- Add lifecycle records outside `domain`: generated proof batch/proposals and
  proof receipt; batch/revision/decision records; immutable snapshot; service
  policy request/receipt.
- Add narrow ports for verified generated-batch recovery, direct-author source
  commitment lookup, service decision policy, and artifact view. Do not add an
  artifact repository.
- Add exactly two events: `study_artifact.proposal_batch_recorded@1` and
  `study_artifact.decision_recorded@1`.
- Add exactly four authority-safe commands:
  - `record_generated(run_id, context, expected_sequence)`: SERVICE-only and no
    caller-authored content/provenance/success;
  - `record_human_revision(content, provenance, target_artifact_id, context,
    expected_sequence)`: HUMAN-only;
  - `record_human_decision(revision_id, decision, supersedes_revision_id,
    context, expected_sequence)`: HUMAN-only;
  - `apply_service_decision(revision_id, context, expected_sequence)`:
    SERVICE-only and outcome supplied only by injected policy.

## Invariants

- Proposal batches are atomic, homogeneous by generated/human origin, bounded
  to 1..24, use contiguous ordinals, and contain each artifact at most once.
  Human batches contain exactly one revision.
- New artifact IDs derive from batch+ordinal and have no prior. Revisions of an
  existing artifact preserve its ID/kind and name the current lineage head.
  A batch may mix new and existing lineages but not revise one artifact twice.
- Recompute every revision ID through the canonical TUT-04A aggregate boundary.
- Flashcard `parent_ordinal` is proposal scaffolding and resolves only to a lower
  ordinal in the same batch. Persist the resulting canonical
  `parent_artifact_id` in lifecycle metadata. A later revision inherits that
  relation; reject clearing or changing it unless a trusted batch resolves to
  the same parent. Never infer a new parent across batches.
- Every new revision begins proposed. Decisions are terminal. Reject never
  supersedes. Accept requires the exact current accepted predecessor when one
  exists and atomically marks it superseded.
- Generated recording is SERVICE-only. Direct authoring requires an existing
  HUMAN interaction in the same session plus exact source commitments. MODEL
  cannot write or decide.
- SERVICE callers cannot supply decision outcomes or receipts. Policy receipts
  bind the exact request/result with portable non-secret identifiers and
  lowercase SHA-256 fingerprints.
- Exact retries resolve before proof/policy calls and sequence checks. Same key
  with a different fingerprint is terminal conflict. Append races fail
  retryably unless the exact command committed.
- Decoder checks envelope-local invariants; reducer repeats every stateful
  authority, lineage, status, session, source-revision/chunk/span commitment,
  and supersession invariant during replay for generated and human proposals.
- Projection is the sole artifact read model and exposes history, pending,
  deterministic collections of current accepted revisions grouped/filtered by
  kind, decision, and durable parent-artifact lookup.
- Exact committed retry never re-runs policy, and stale sequence fails before
  policy. After an uncommitted append race, a retry may re-invoke only a
  deterministic/idempotent policy keyed by the stable decision event/request ID
  and must receive the same bound result; no ad-hoc checkpoint store is added.

## Verification

- `.venv/bin/ruff check src`
- `MYPYPATH=src .venv/bin/mypy --strict src`
- Existing domain/event-state/session/study-context contract tests.
- `git diff --check`

## Report

Report public names, exact schemas, commands run/results, and any contract that
could not be implemented. Do not edit tests, commit, or delegate.
