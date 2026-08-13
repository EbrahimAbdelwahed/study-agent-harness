# Task Bead: HR-04 Minimal Decision Trace and diagnostics

Status: Open
Priority: P1
Type: task
Depends On: HR-03-executor-recovery

## Outcome

Harness persists a separate append-only Decision Trace of observable execution choices and bounded redacted diagnostics for recovery. Trace fields are allowlisted, diagnostics expire after 14 days, and optional telemetry loss cannot alter execution.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-04-decision-trace.md`: TraceRecord, TraceStorePort, SQLite append-only storage, redaction/retention, and optional OpenTelemetry isolation.
- `specs/future-runtime/README.md`: trace/domain-event separation, privacy deny-list, diagnostic retention, and replay invariants.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-04-decision-trace.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

The trace is a local allowlisted audit stream with deterministic redaction and no mandatory telemetry dependency. Execute in one fresh Luna xhigh context.

## Context

HR-04 consumes HR-03 hooks and creates an operational audit stream distinct from canonical domain events. It must never store prompts, excerpts, outputs, secrets, raw personal identity, or private model reasoning.

## What To Do

- Add trace contracts/service, TraceStorePort, SQLite trace storage, and diagnostics retention/redaction modules named by the slice.
- Persist only trace/workflow/Job/attempt/capability IDs, correlation/causation, transitions, validators/outcomes, safe errors, fingerprints, and timestamps.
- Enforce append-only ordering, safe error translation, nested deny-list scanning, 14-day diagnostic expiry, and exporter failure isolation.
- Add optional OpenTelemetry adapter coverage without making telemetry required or outcome-affecting.

## Likely Files / Packages

- `src/study_agent/trace/contracts.py`, `src/study_agent/trace/service.py`: TraceRecord and append/read behavior.
- `src/study_agent/ports/trace.py`: TraceStorePort.
- `src/study_agent/adapters/sqlite/trace_store.py`: separate append-only SQLite storage.
- `src/study_agent/diagnostics/retention.py`, `src/study_agent/diagnostics/redaction.py`: bounded operational payload handling.
- `tests/unit/trace/test_contracts.py`, `tests/contract/trace/test_store.py`: contract coverage.
- `tests/integration/test_job_decision_trace.py`, `tests/integration/test_optional_otel_loss.py`: runtime/exporter behavior.
- `tests/adversarial/test_trace_redaction.py`: nested leak and retention scans.

## Acceptance Criteria

- [ ] Trace serialization contains only the approved observable allowlist and is deterministic, append-only, separately stored, and linked by correlation/causation IDs.
- [ ] Prompts, excerpts, outputs, secrets, raw personal identity, chain-of-thought, and learner/product facts are rejected from trace, errors, exports, and diagnostics.
- [ ] Redacted diagnostics expire after 14 days; exporter failure or optional telemetry loss leaves Job outcomes unchanged.
- [ ] Trace replay preserves ordering and never becomes a domain event or product projection.
- [ ] Focused redaction/retention test gate passes; an independent semantic/security review gate confirms deny-list coverage and stream separation.

## Verification

- `.venv/bin/python -m pytest tests/unit/trace/test_contracts.py tests/contract/trace/test_store.py tests/integration/test_job_decision_trace.py tests/adversarial/test_trace_redaction.py tests/integration/test_optional_otel_loss.py`: all focused tests pass.
- `.venv/bin/python -m pytest`: global offline suite remains green.
- `.venv/bin/python -m ruff check src/study_agent/trace src/study_agent/ports/trace.py src/study_agent/adapters/sqlite/trace_store.py src/study_agent/diagnostics tests/unit/trace tests/contract/trace tests/integration/test_job_decision_trace.py tests/adversarial/test_trace_redaction.py`: lint passes.
- `.venv/bin/python -m mypy`: strict typing remains green.
- `git diff --check`: clean.

## Out Of Scope

- Domain-event projections, learner evidence, full prompt/excerpt/output storage, remote diagnostics, mandatory OpenTelemetry, Cardine, web/sealed workflow, and edits outside listed paths.

## Invariants

- Decision Trace is separate audit evidence, not learner truth or a canonical fact ledger.
- Optional telemetry is loss-insensitive.
- Diagnostic payloads are operational and time-bounded; minimal trace survives until repository deletion.

## Stop Conditions

- Stop and report if a new field lacks an allowlist/privacy rule or if trace would become a domain event.
- Stop if optional telemetry requires credentials or network in default tests.

## Review Gate

Focused tests and an independent semantic/security review must both pass before HR-05 is dispatched.

## Notes / Handoff

- HR-05 consumes trace hooks while proving one outer lifecycle owner.
