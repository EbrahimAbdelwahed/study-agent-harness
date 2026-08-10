# HR-04 — Minimal Decision Trace and Diagnostics

## Outcome

Persist a separate append-only Decision Trace for observable execution choices
and bounded redacted diagnostics for recovery, without creating a second domain
fact ledger or storing private model reasoning.

## Non-goals

No domain-event projection, learner evidence, full prompt/excerpt/output,
secret, raw personal identity, chain-of-thought, mandatory telemetry, or remote
diagnostic sink.

## Contract and API seam

`src/study_agent/trace/contracts.py` defines `TraceRecord` with trace,
workflow, Job, attempt, capability, correlation/causation, transition,
validator/outcome, safe error, fingerprints, and timestamp fields.
`src/study_agent/ports/trace.py:TraceStorePort` appends and reads the separate
stream. `src/study_agent/adapters/sqlite/trace_store.py:SQLiteTraceStore`
implements append-only storage. `src/study_agent/diagnostics/retention.py`
redacts and expires diagnostic payloads after 14 days. OpenTelemetry is an
optional loss-insensitive adapter.

## Files and tests

- Add `src/study_agent/trace/{contracts.py,service.py}`,
  `src/study_agent/ports/trace.py`, SQLite trace storage, and diagnostics
  retention/redaction modules.
- Add `tests/unit/trace/test_contracts.py`,
  `tests/contract/trace/test_store.py`,
  `tests/integration/test_job_decision_trace.py`,
  `tests/adversarial/test_trace_redaction.py`, and
  `tests/integration/test_optional_otel_loss.py`.

## Dependencies

HR-01 contracts and HR-03 executor hooks; HR-02 SQLite transaction patterns.

## Removal condition

Diagnostics remain operational and expire. Trace remains audit evidence. No
future slice may promote either into a Cardine/product projection.

## Review surface

Review field allowlist/deny-list, append-only ordering, correlation links,
safe-error mapping, retention job, and exporter failure isolation.

## Exact verification

```bash
.venv/bin/python -m pytest tests/unit/trace/test_contracts.py tests/contract/trace/test_store.py tests/integration/test_job_decision_trace.py tests/adversarial/test_trace_redaction.py tests/integration/test_optional_otel_loss.py
```

Then run full offline pytest and package import-boundary tests.

## Risks

New fields can accidentally leak content or identity. Redaction tests must
scan serialized records, exports, exception payloads, and optional exporter
requests, including nested unknown values.

## Definition of done

Trace replay is deterministic, append-only, separate from domain events, and
contains only approved observable fields; diagnostics expire at 14 days;
optional telemetry loss never changes Job outcomes; leak tests pass.
