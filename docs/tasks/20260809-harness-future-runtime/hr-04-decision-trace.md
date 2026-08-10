# Task Bead: hr-04-decision-trace Minimal Decision Trace and diagnostics

Status: Open
Priority: P1
Type: task
Depends On: hr-03-executor-recovery
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

Harness persists a separate append-only Decision Trace of observable choices and bounded redacted diagnostics with 14-day expiry and loss-insensitive optional telemetry.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- HR-04 TraceRecord, TraceStorePort, SQLite append-only storage, redaction/retention, and telemetry isolation.
- README trace/domain-event separation, privacy deny-list, diagnostic retention, and replay.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-04-decision-trace.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Local allowlisted audit and redaction fit one fresh Luna xhigh context.

## Context

HR-04 consumes executor hooks and creates operational audit evidence distinct from canonical domain events.

## What To Do

- Add trace contracts/service/port, SQLite store, and diagnostics retention/redaction.
- Persist only approved observable fields; reject content, identity, secrets, and private reasoning.
- Add append-order, nested deny-list, 14-day expiry, and optional exporter-loss fixtures.

## Likely Files / Packages

- src/study_agent/trace/contracts.py
- src/study_agent/trace/service.py
- src/study_agent/ports/trace.py
- src/study_agent/adapters/sqlite/trace_store.py
- src/study_agent/diagnostics/retention.py
- src/study_agent/diagnostics/redaction.py
- tests/unit/trace/test_contracts.py
- tests/contract/trace/test_store.py
- tests/integration/test_job_decision_trace.py
- tests/adversarial/test_trace_redaction.py
- tests/integration/test_optional_otel_loss.py

## Acceptance Criteria

- [ ] Trace is deterministic, append-only, separate, and allowlisted; forbidden content and identity never serialize.
- [ ] Diagnostics expire after 14 days and optional telemetry loss leaves outcomes unchanged.
- [ ] Focused trace/redaction test gate and independent semantic/security review gate both pass.

## Verification

- `.venv/bin/python -m pytest tests/unit/trace/test_contracts.py tests/contract/trace/test_store.py tests/integration/test_job_decision_trace.py tests/adversarial/test_trace_redaction.py tests/integration/test_optional_otel_loss.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/trace src/study_agent/ports/trace.py src/study_agent/adapters/sqlite/trace_store.py src/study_agent/diagnostics tests/unit/trace tests/contract/trace tests/integration/test_job_decision_trace.py tests/adversarial/test_trace_redaction.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- Domain projections, learner evidence, full prompt/output storage, remote diagnostics, mandatory telemetry, Cardine, web/sealed workflow, and paths outside the allowlist.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
