# Task Bead: typed-tools-reference-harness Implement exact typed tools and reference harness

Status: Open
Priority: P1
Type: task
Depends On: grounding-ask-service
Run ID: `20260712-oss-harness-v01-batch7`
Spec: `docs/specs/oss-harness-v0-1-typed-tools-and-reference-harness.md`

## Worker Profile

create `typed-tool-harness-worker`

Rationale:

No reusable specialization selected yet.

## Context

External agents and the reference harness must consume identical application services through enforced portable contracts.

## What To Do

- Implement strict JSON schema validator, tool manifest/result/error/effect/idempotency and StudyEvent contracts.
- Implement exactly seven thin context-authorized tools and unique registry.
- Implement StudyHarness as an async lifecycle-event adapter over GroundingAskService.
- Prove direct/tool/harness byte/domain parity, authorization, recovery, injection and no-eighth-tool behavior.

## Likely Files / Packages

- ports/tools.py and tools/contracts.py, schema.py, registry.py, builtin.py
- application/harness.py
- tool/harness unit/contract/integration/architecture tests

## Acceptance Criteria

- [ ] Exact seven manifests are enforced and public/internal registries are separate.
- [ ] Context authority cannot be forged by arguments.
- [ ] Inputs/outputs/capabilities/errors/idempotency validate around effects.
- [ ] Direct/tool/harness append once and return identical canonical answers/events.

## Verification

- `.venv/bin/python -m pytest tests/unit/tools tests/contract/tools tests/integration/test_tool_harness_parity.py tests/architecture`: expected to pass or produce documented output
- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output

## Out Of Scope

- CLI/export, MCP/HTTP/Tau, token streaming, provider selection, product.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
