# Feature Spec: OSS Harness v0.1 Typed Tools and Reference Harness

Status: Implemented
Owner: orchestrator
Date: 2026-07-12

Implementation review: [`../reviews/20260712-oss-harness-v01-batch7.md`](../reviews/20260712-oss-harness-v01-batch7.md)
Run ID: `20260712-oss-harness-v01-batch7`

## Goal

Expose the grounded-session spine through one ordinary application use case, an exact seven-tool framework-neutral registry, and a minimal reference harness, while adding the missing immutable course aggregate so every source/session belongs to canonical event-sourced course state.

## Problem

The approved domain services exist but cannot yet be consumed through the specified external-agent or reference-harness boundary. Course profiles are not canonical event state, public tool schemas are absent, and there is no single ask orchestration service that safely owns execute/recover/finalize. Implementing wrappers before these seams would create orphan course data, duplicate study behavior, or unsafe retries.

## Architectural Decisions

1. `course.created@1` is the only v0.1 course mutation; no update/delete/version API.
2. Source ingestion and session start reject courses with no canonical profile.
3. Public `StudyToolRegistry` and internal playbook `RuntimeRegistries` are separate. `grounding.ask` is never a playbook executor.
4. `GroundingAskService` is the single direct use case. Public `grounding.ask` and `StudyHarness.ask` are thin adapters over the same instance.
5. Public arguments never carry principal/course/session/correlation/model/run authority; trusted `ExecutionContext` is a separate invocation parameter.
6. Duplicate-run behavior is explicit: finalized returns the same answer; completed/valid termination recovers and finalizes; suspended/running/failed return typed safe errors and never repeat effects.
7. `StudyEvent` is an ephemeral closed lifecycle vocabulary, not a canonical `DomainEvent` or model-token stream.

## In Scope

- Strict `course.created@1` codec/reducer/service/view and course existence guards.
- Canonical course-profile JSON composition for prompts and tool output.
- Request-bound internal `session.get_context` and `source.search` playbook executors that close over trusted services/context.
- Deterministic run identity, exact pins/read dependencies, execute/recover/finalize state machine.
- Immutable JSON-only `ToolManifest`, `ToolResult`, `ToolError`, `StudyEvent`, effects, idempotency, schema and capability contracts.
- Exact registry: `course.get`, `source.list`, `source.search`, `citation.resolve`, `session.get_context`, `session.record_note`, `grounding.ask`, all `1.0.0`.
- Minimal async-iterator `StudyHarness` yielding accepted/completed/failed/suspended lifecycle events from the same ask service.
- Direct/tool/harness parity, recovery, authorization and schema conformance tests.

## Out of Scope

- CLI/export, MCP/HTTP/Tau, provider/model selection, token streaming, generic agents, hosted auth/RBAC, course edits/deletion, telemetry, or product work.

## Course Aggregate

`course.created@1` payload is the exact complete `CourseProfile`: ID, title, language, optional exam date, assessment styles, learning goals, source policy and terminology policy. Envelope course ID must match profile ID; only trusted HUMAN/SERVICE actors append. Event ID and command fingerprint are deterministic. Same profile is idempotent; same course ID with different profile conflicts. Projection key `course` coexists with `sources`, `chunks`, `sessions`, `interactions`, and `answers` and replay remains byte-identical.

`CourseViewPort.get(course_id)` is projection-only. `TextIngestionService.ingest` and `SessionService.start` require the view/guard and reject missing courses. Existing unreleased fixtures create a course first.

## Grounding Ask Service

`GroundingAskService.ask(question, context) -> GroundingAskResult`:

- requires active canonical course/session, `study:ask`, and a non-empty trusted idempotency key;
- loads canonical CourseProfile, source policy, bounded continuation summary, retrieval catalog/index receipt;
- creates request-scoped internal ToolExecutors; they ignore/reject authority in arguments and use the captured context;
- derives a deterministic RunId from course/session/idempotency/question fingerprint and exact skill/playbook/prompt/model/state/tool pins;
- binds source revision-set and continuation summary fingerprints as read dependencies;
- executes the canonical `grounded_answer@1` flow when no run exists;
- on duplicate, recovers only completed or successful deterministic termination and finalizes without repeating context/search/model effects;
- returns suspended/running/failed/incompatible states as stable safe errors, never a new run;
- delegates the only canonical answer commit to `GroundedSessionFinalizer` and returns its `AnswerRecord` plus deterministic lifecycle events.

No prompt, retrieval, grounding, citation, provenance, fallback or persistence behavior is reimplemented in wrappers.

## Public Tool Contracts

Every manifest contains name/version, exact input/output schema, effect (`read_only | canonical_write | orchestration`), required host capabilities, emitted audit/event kinds, declared safe error codes, and idempotency mode (`not_applicable | required`). Schemas use an implemented strict subset and `additionalProperties:false`; semantic branded-ID/date/citation validation follows through domain decoders. Registry validates input before effects and output before return; unknown/duplicate tools, bool-as-int, non-finite numbers and unknown fields fail closed.

Arguments:

- `course.get {}`
- `source.list {include_superseded?}`
- `source.search {query, limit?, revision_ids?, minimum_trust_level?, source_kinds?, source_roles?, include_superseded?}`
- `citation.resolve {citation:{source_id,revision_id,chunk_id,start_offset,end_offset}}`
- `session.get_context {}`
- `session.record_note {content}`
- `grounding.ask {question}`

Context authority fields and provider/model/prompt/pin selectors are forbidden. `source.list` returns manifests only, never blob locations/content. Citation resolution generates canonical locator/quote. Empty list/search is successful structured output. Writes require idempotency key. Required capabilities are `study:read`, `study:write`, or `study:ask`; MODEL principals require explicit host grants like any other principal.

Safe error vocabulary: `invalid_arguments`, `unauthorized`, `not_found`, `conflict`, `retryable_conflict`, `incompatible_runtime`, `execution_failed`. Provider details, credentials, source text and raw exceptions never enter errors.

## Reference Harness

`StudyHarness.ask(question, context)` calls the same `GroundingAskService`. It emits only validated coarse events: `grounding.accepted`, `grounding.completed`, `grounding.suspended`, or `grounding.failed`. Tool result and harness stream carry the exact same service events. No token deltas, generic event bus, trace mirroring, autonomous planning or recursive tool invocation.

## Acceptance Criteria

- [x] Course creation is typed, idempotent and replayable; orphan source/session writes fail.
- [x] Public registry contains exactly seven unique versioned tools; internal runtime registry remains separate.
- [x] Context authority cannot be supplied or overridden through tool arguments.
- [x] Every manifest schema/effect/capability/error/idempotency declaration is enforced before/after effects.
- [x] All seven tools are course/session scoped and preserve citation/provenance/session invariants.
- [x] `GroundingAskService`, public `grounding.ask`, and `StudyHarness.ask` produce the same canonical AnswerRecord/provenance and append exactly one event batch.
- [x] Retry across surfaces returns the same answer and makes zero additional model/tool calls; changed request conflicts.
- [x] Completed/terminated runs recover; running/failed/suspended/incompatible runs never silently re-execute.
- [x] Prompt-injection content cannot add an eighth tool or modify manifests/capabilities/schema.
- [x] Harness events are ephemeral, validated and never stored as domain events.
- [x] Default tests are offline/provider-neutral and no product/MCP/HTTP/Tau scope is added.
- [x] Unit, contract, integration, architecture, Ruff, mypy and diff gates pass.

## Verification

- Unit: course codec/reducer/service, run identity/state machine, schemas/manifests/registry/events.
- Contract: exact seven tools, JSON input/output, effects, errors, capabilities, idempotency and immutable results.
- Integration: course creation, all tool services, supported/insufficient ask, crash recovery and direct/tool/harness parity.
- Architecture: public/internal registry separation and no provider/product/transport imports in core boundaries.
- Full: offline pytest, Ruff, mypy, diff check and independent semantic review.

## Task Beads

- `course-profile-kernel`: immutable course event/reducer/view/service and existence guards.
- `grounding-ask-service`: request-scoped internal executors and deterministic execute/recover/finalize state machine.
- `typed-tools-reference-harness`: strict contracts, exact seven wrappers/registry, harness events and parity/adversarial tests.
