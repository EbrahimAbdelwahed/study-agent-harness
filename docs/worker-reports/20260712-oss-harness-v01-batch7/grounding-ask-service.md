# Worker Report: grounding-ask-service

Status: complete
Run ID: `20260712-oss-harness-v01-batch7`
Task: `docs/tasks/20260712-oss-harness-v01-batch7/grounding-ask-service.md`
Brief: `docs/worker-briefs/20260712-oss-harness-v01-batch7/grounding-ask-service.md`
Agent: grounding_ask_service_impl
Reported: 2026-07-12 03:36

## Files Changed

- application/grounding_ask.py: canonical auth, identity, dependency and execute/recover/finalize state machine
- tools/playbook_bridge.py: request-bound trusted internal context/search executors
- playbooks/builtin/grounded_answer_flow.py: removes authority-bearing tool bindings
- tests/integration/test_grounding_ask_service.py: supported, insufficient, retry, recovery, auth and failure coverage

## Behavior Implemented

- One provider-neutral ask use case owns grounded execution and canonical finalization.
- Duplicate completed runs recover without repeated effects; unsafe states fail explicitly.

## Verification

- .venv/bin/python -m pytest: 267 passed, 1 expected skipped
- .venv/bin/python -m ruff check .: passed
- .venv/bin/python -m mypy: passed across 123 source files

## Open Questions Or Blockers

- None.

## Follow-up Beads Needed

- Independent review before exposing the service through public tools and harness.
