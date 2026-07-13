# Task Bead: model-adapter-contracts Implement scripted and generic OpenAI-compatible model adapters

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260711-oss-harness-v01-batch5`
Spec: `docs/specs/oss-harness-v0-1-grounded-answer-and-model-adapters.md`

## Worker Profile

create `model-adapter-worker`

Rationale:

No reusable specialization selected yet.

## Context

The existing ModelPort needs trustworthy invocation provenance and reusable conforming offline/HTTP adapters without allowing transports to own study behavior.

## What To Do

- Tighten provider-neutral model response/invocation, finish reason, error, role, usage, and stream-event invariants without provider leakage.
- Implement a strict FIFO ScriptedModel with immutable request history, deterministic generate/stream/cancel behavior, and exhaustion checks.
- Implement a dependency-free OpenAI-compatible chat-completions adapter behind an injected bounded HTTP transport.
- Exclude metadata from HTTP payloads, validate responses strictly, map safe retryable errors, and redact credentials/content from reprs and exceptions.
- Add reusable conformance tests and an explicitly skipped configuration-only real smoke fixture.

## Likely Files / Packages

- `src/study_agent/ports/model.py`: portable model contracts
- `src/study_agent/adapters/model/`: scripted and OpenAI-compatible adapters
- `tests/contract/model/`: reusable conformance suite
- `tests/unit/adapters/model/`: translation, protocol, error, redaction tests
- `tests/integration/test_openai_compatible_smoke.py`: opt-in skipped smoke

## Acceptance Criteria

- [ ] Both adapters satisfy one ModelPort conformance suite with structurally declared capabilities.
- [ ] Scripted calls are exact, deterministic, immutable, and never access environment/network.
- [ ] HTTP construction/import is inert and all default translation tests use an injected fake transport.
- [ ] Metadata and secret/content sentinels never appear in HTTP bodies, reprs, or safe public errors.
- [ ] Unsupported streaming/cancellation is explicit and never advertised; no provider/model-name branching exists.

## Verification

- `.venv/bin/python -m pytest tests/contract/model tests/unit/adapters/model tests/integration/test_openai_compatible_smoke.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/ports/model.py src/study_agent/adapters/model tests/contract/model tests/unit/adapters/model`: expected to pass or produce documented output
- `.venv/bin/python -m mypy src/study_agent/ports/model.py src/study_agent/adapters/model tests/contract/model tests/unit/adapters/model`: expected to pass or produce documented output

## Out Of Scope

- Prompt composition, grounding/retrieval policy, provider SDKs, retries, live default calls, true HTTP streaming/cancellation, and product scope.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
