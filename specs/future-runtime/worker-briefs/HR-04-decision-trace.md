# Worker Brief: HR-04

## Assignment

Implement `HR-04-decision-trace` from `specs/future-runtime/slices/HR-04-decision-trace.md`.

Worker target: Luna xhigh. Execute only this bead after HR-03 is complete.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-04-decision-trace.md`
- `specs/future-runtime/beads/HR-04-decision-trace.md`
- HR-03 executor hooks and existing SQLite/diagnostic serialization conventions

## Scope

You may change:

- `src/study_agent/trace/contracts.py`
- `src/study_agent/trace/service.py`
- `src/study_agent/ports/trace.py`
- `src/study_agent/adapters/sqlite/trace_store.py`
- `src/study_agent/diagnostics/retention.py`
- `src/study_agent/diagnostics/redaction.py`
- `tests/unit/trace/test_contracts.py`
- `tests/contract/trace/test_store.py`
- `tests/integration/test_job_decision_trace.py`
- `tests/adversarial/test_trace_redaction.py`
- `tests/integration/test_optional_otel_loss.py`

Do not change:

- Paths outside the allowlist, including canonical event projections, learner evidence, web/sealed workflows, Cardine, mandatory telemetry, credentials, and dependencies.

## Requirements

- Persist only the approved observable TraceRecord fields; keep append-only ordering and separate storage.
- Reject prompts, excerpts, outputs, secrets, raw identity, chain-of-thought, learner facts, and nested unknown sensitive values.
- Expire redacted diagnostics after 14 days and isolate optional telemetry loss from Job outcomes.

## Acceptance Criteria

- Focused trace/redaction/retention tests pass; trace replay is deterministic and never a domain event.
- Separate test and independent semantic/security review gates both pass.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/unit/trace/test_contracts.py tests/contract/trace/test_store.py tests/integration/test_job_decision_trace.py tests/adversarial/test_trace_redaction.py tests/integration/test_optional_otel_loss.py
.venv/bin/python -m ruff check src/study_agent/trace src/study_agent/ports/trace.py src/study_agent/adapters/sqlite/trace_store.py src/study_agent/diagnostics tests/unit/trace tests/contract/trace tests/integration/test_job_decision_trace.py tests/adversarial/test_trace_redaction.py
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return files changed, behavior implemented, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
