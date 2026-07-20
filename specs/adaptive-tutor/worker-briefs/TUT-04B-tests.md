# Worker Brief: TUT-04B tests

## Goal

Independently pin the canonical artifact proposal/decision lifecycle, replay,
authority boundaries, idempotency, and views.

## Allowed Files

- `tests/unit/artifacts/test_lifecycle_events.py`
- `tests/unit/artifacts/test_lifecycle_projection.py`
- `tests/unit/artifacts/test_lifecycle_service.py`
- `tests/unit/artifacts/test_lifecycle_view.py`
- `tests/architecture/test_artifact_lifecycle_boundaries.py`

## Forbidden Files

- Production, docs/specs, other tests, capabilities/prompts/playbooks/adapters,
  CLI/export, configuration, dependencies, and `sbobby-web`.

## Acceptance Criteria

- Exact event codecs reject extra fields, forged IDs/fingerprints, mismatched
  origin/actor/session, MODEL writers, invalid receipt unions, content carrying
  lifecycle state, and decisions carrying content/provenance.
- Generated public signature accepts run identity only; failed/tampered proof
  cannot append; exact retry does not invoke proof twice; same retry key with a
  different run conflicts.
- Human authoring requires HUMAN, exact same-session human interaction, and
  exact source/chunk/revision commitments; SERVICE/MODEL cannot bypass it.
- Batch tests cover mixed new/existing lineages, current-head prior, preserved
  kind/identity, contiguous ordinals, maximum 24, duplicate artifact rejection,
  and lower same-batch parent resolution. A single-item human revision and a
  later generated revision retain the canonical parent artifact across batches;
  clearing or changing the relation fails.
- Hostile replay rejects generated and human proposals whose source commitment
  names a missing/wrong-course source revision or chunk, or an invalid span.
- Decision matrix covers HUMAN accept/reject, SERVICE injected policy, MODEL
  denial, receipt binding/secrets, terminal decisions, reject-with-supersession
  rejection, exact accepted-predecessor supersession, and atomicity.
- Exact committed retry and stale sequence do not run policy. Append-race retry
  may re-invoke only a deterministic/idempotent policy using the stable decision
  request/event identity and must get the same bound result. Concurrent accepts
  still cannot both commit.
- Replay/view covers history, pending, current accepted by kind, durable
  decisions, superseded history, and durable parent-artifact lookup across
  revisions and batches; it must not fall back to batch-local ordinal lookup.
- Architecture test pins inward imports, event projection as sole owner, and
  unchanged seven StudyTools/two built-in tutor capabilities.

## Verification

- New focused tests, Ruff, strict mypy, relevant existing event-state tests, and
  `git diff --check`.

## Report

Report concrete production mismatches as findings. Do not edit production,
commit, or delegate.
