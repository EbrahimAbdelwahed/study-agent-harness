# Worker Brief: GAP-01 essential operational registry tracer

## Assignment and Status

Implement only the essential GAP-01 registry subset. This proves strict local
observation/deduplication but does not complete GAP-01: retention, rate policy,
resolution, workaround receipts, and export state remain deferred.

## Allowed Files

- `src/study_agent/feedback/{__init__,contracts,service,view}.py`.
- `src/study_agent/ports/capability_gap.py`.
- `src/study_agent/adapters/sqlite/capability_gap_store.py`.
- `tests/unit/feedback/test_capability_gap_contracts.py`.
- `tests/unit/feedback/test_capability_gap_service.py`.
- `tests/integration/test_capability_gap_sqlite.py`.
- `tests/architecture/test_capability_gap_boundaries.py`.

No existing file may change.

## Closed Vocabulary

- `GapCategory`: `input_format`, `output_format`, `study_behavior`,
  `integration`, `accessibility`, `performance`, `reliability`.
- `RequestedOperationKind`: `ingest_source`, `extract_text`, `preserve_tables`,
  `generate_study_artifact`, `assess_learner`, `integrate_service`,
  `render_accessibly`, `reduce_latency`, `recover_operation`.
- `SafeTargetKind`: `text`, `markdown`, `pdf`, `image`, `audio`, `video`,
  `tabular`, `external_service`, `study_session`, `study_artifact`, `runtime`.
- `TrustedLimitationCode`: `unsupported_format`, `missing_capability`,
  `missing_integration`, `inaccessible_content`, `resource_limit`,
  `transient_failure`, `reliability_failure`.
- `ImpactKind`: `blocked`, `degraded`, `workaround_available`.
- `VerificationKind`: `unverified_request`, `verified_runtime_failure`.
- `GapDisposition`: `recorded`, `deduplicated`.

## Exact Values and Codecs

- `TrustedLimitationReceipt(contract_identity: str, contract_major: int,
  limitation_code: TrustedLimitationCode, failure_fingerprint: str)`: strict
  opaque contract identity, positive non-bool major, lowercase SHA-256. It is
  supplied only through trusted service context and is not model payload.
- `CapabilityGapDimensions(schema_version=1, category,
  requested_operation_kind, safe_target_kind, limitation_code,
  relevant_contract_identity, contract_major)`. Exact canonical JSON field set;
  no impact/receipt/idempotency/identity/timestamp.
- `GapKeyV1(value)`: derive only as SHA-256 of
  `b"study-agent-gap-key-v1\0" + canonical_dimensions_bytes`. Decode recomputes
  and rejects mismatch/collision.
- `CapabilityGapObservation(category, requested_operation_kind,
  safe_target_kind, impact_kind)`: closed values only; persistent codec has
  exact fields and no free text.
- `CapabilityGapWriteContext(harness_version, correlation_id,
  idempotency_fingerprint, observed_at, limitation_receipt=None)`: trusted only;
  bounded opaque harness version/correlation, SHA-256 idempotency, UTC-aware
  timestamp. Without receipt force `unverified_request` and limitation code
  `missing_capability`; with receipt require matching contract identity/major.
- `CapabilityGapAggregate`: gap key, canonical dimensions, verification,
  impact, first/last UTC timestamps and positive occurrence count. It contains
  no report or observation identity. Strict
  canonical codec and full decode/re-encode equality.
- The only per-call id is `report_id = SHA256(
  b"study-agent-gap-report-v1\0" + gap_key.encode() + b"\0" +
  idempotency_fingerprint.encode())`; the service returns the current call's
  report id and never persists it inside aggregate payload.

Reject unknown/missing/noncanonical fields, bool-as-int, free text, paths,
filenames, secrets, source/prompt bodies, commands, executable/provider fields,
caller identities, priority/severity/status/resolution and oversized text before
store calls.

## Port and Service

- `CapabilityGapStore.create_or_increment(gap_key: str, report_id: str,
  payload: bytes) -> tuple[bytes, bool]`: returns canonical aggregate bytes and
  `created_observation`; exact report retry returns existing bytes/False;
  distinct report for same key atomically increments once; conflicting
  dimensions fail `gap_key_collision`. `payload` is always a canonical proposed
  aggregate with occurrence_count=1 and identical first_seen/last_seen. On a
  new report for an existing key the store preserves first_seen, sets last_seen
  to the proposal timestamp, adds exactly one occurrence, and preserves the
  existing verification/impact unless the proposal differs—in this essential
  tracer any differing verification/impact raises
  `CapabilityGapValidationError("aggregate_variant_unsupported")` before
  mutation rather than inventing merge policy. `GapKeyV1` remains the exact ADR
  key and does not add impact or verification.
- `load(gap_key: str) -> bytes`; a missing key raises
  `CapabilityGapUnavailableError("gap_not_found")`. No
  list/export/update/delete API.
- `CapabilityGapService.record(observation, context) ->
  CapabilityGapCompactView`; `get(gap_key) -> CapabilityGapDetailView` is
  trusted local query. Define closed safe errors: validation, collision,
  corruption, unavailable; no underlying exception text.

## SQLite Contract

Path-backed DB only, existing no-follow identity guard pattern. Own exactly two
STRICT tables:

```sql
capability_gap_aggregates(gap_key TEXT PRIMARY KEY, payload BLOB NOT NULL)
capability_gap_reports(report_id TEXT PRIMARY KEY, gap_key TEXT NOT NULL)
```

One `BEGIN IMMEDIATE` transaction validates schema/types, checks report
idempotency, decodes existing aggregate, checks exact dimensions, increments and
updates payload, inserts report id, then commits. Roll back on any failure.
Restart/races converge. No deletion/retention in this tracer.

Public safe exceptions are exactly `CapabilityGapValidationError(ValueError)`,
`CapabilityGapCollisionError(RuntimeError)`,
`CapabilityGapCorruptionError(RuntimeError)`, and
`CapabilityGapUnavailableError(RuntimeError)`; messages are fixed codes only
and never include SQLite/provider/input text.

The canonical aggregate payload contains exactly:
`schema_version=1`, `gap_key`, `dimensions`, `verification_kind`, `impact_kind`,
`first_seen`, `last_seen`, and `occurrence_count`. No report id, receipt,
idempotency, correlation, harness version, authority, resolution, or export
state is stored in this essential payload.

## Tests and Stop Conditions

Prove exact retry, distinct aggregation, PDF extract-vs-tables distinction,
restart, race, schema/tamper/collision/privacy rejection, and separation from
events/StudyTools/model/network. Stop rather than add an existing export or any
deferred GAP behavior. Do not mark GAP-01 Done.
