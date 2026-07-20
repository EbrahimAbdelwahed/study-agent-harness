# Handoff: TUT-04 closure and next lanes

Date: 2026-07-18 11:35
Area: study-agent

## Current State

TUT-04 and TUT-05 are complete. TUT-04F is full-suite green and independently
reviewed. Work stops here so the next lane can be selected deliberately.

## Completed

- Public lesson ingestion, deterministic planning, isolated hybrid worker,
  verified owner/proof recovery through `VerifiedGeneratedBatchAdapter`, artifact
  proposal, HUMAN accept/revision/reject, exact retries, and replay/export.
- Public grounded exam analysis, exact evidence mapping, verified blueprint
  recovery, HUMAN decision, retry, and replay/export.
- Bounded redacted compact host trace plus opaque evidence-handle assertions.
- Deterministic eval report with worker-view metrics and canonical Export V2
  decisions/provenance.

## Remaining

- Choose between adaptive-tutor lanes TUT-06B/TUT-06C, recall lane TUT-07A, or
  self-proposing harness lane GAP-01.
- GAP-04A is also dependency-ready but optional; it should not precede GAP-01
  unless workaround registration is explicitly prioritized.
- Resolve the repository-wide strict-mypy backlog (120 errors in 14 older test
  files) as a separate mechanical quality batch; do not weaken strictness.

## Important Context

- GAP critical path is GAP-01 -> GAP-02 -> GAP-05A -> GAP-05B -> GAP-05C ->
  GAP-06. GAP-03 additionally depends on TUT-06; GAP-07 closes after GAP-03 and
  GAP-06.
- Preserve event sourcing as canonical state, skill/playbook behavior, technical
  adapters only, model-agnostic core, and exact seven StudyTools.
- Do not touch `sbobby-web`; do not use Claude.

## Verification

- `PYTHONPATH=.:src .venv/bin/python -m pytest -q`: 1558 passed, 2 skipped.
- `.venv/bin/ruff check src tests`: passed.
- TUT-04F strict mypy: passed.
- `uv build`: passed.
