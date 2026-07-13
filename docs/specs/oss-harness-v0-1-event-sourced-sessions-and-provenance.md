# Feature Spec: OSS Harness v0.1 Event-Sourced Sessions and Provenance

Status: Implemented
Owner: orchestrator
Date: 2026-07-11

Implementation review: [`../reviews/20260711-oss-harness-v01-batch6.md`](../reviews/20260711-oss-harness-v01-batch6.md)
Run ID: `20260711-oss-harness-v01-batch6`

## Goal

Persist and resume grounded study sessions from canonical typed events, committing only validated answers with complete trusted provenance and a bounded deterministic continuation summary, while preserving crash safety, idempotency, replay equivalence, and the skill/playbook behavior boundary.

## Problem

The harness can complete a grounded-answer run but has no canonical session mutation path. Existing session types are inert, model provenance is mandatory even when insufficient evidence prevents a model call, retrieval and validator receipts are incomplete, and a side-effecting final ToolStep would create an unsafe effect-before-checkpoint-CAS window. The release needs an event-sourced application finalizer and verified run recovery before typed public tools or CLI can safely consume the behavior.

## Source Inputs

- Parent spec: `docs/specs/oss-study-agent-harness-v0-1.md`
- ADR: [`../decisions/ADR-0002--event-state-skills-playbooks.md`](../decisions/ADR-0002--event-state-skills-playbooks.md)
- Intake/context: private Flywheel build provenance (not distributed)

## Users

- Library authors resuming a local study session without replaying raw chat.
- Researchers auditing which sources, prompt, model, retrieval index, validators, and state pins produced an answer.
- Future reference harness and typed tools, which will invoke these same application services.

## In Scope

- Strict typed event schemas for session start, human/note interaction, validated answer, summary update, suspend, resume, and final end.
- Pure reducers over the existing per-course event stream and a projection-backed `SessionViewPort`.
- Typed answer records linked to session, question interaction, playbook run, exact citations, and provenance.
- Honest deterministic insufficient-evidence answers with no invented model invocation.
- Trusted retrieval receipt fields and validator trace details needed for provenance assembly.
- Verified recovery of completed/terminated-success playbook results from `RunStore` with exact pins, definition, inputs, and read dependencies.
- Application-layer idempotent finalization of a verified run as one atomic event batch.
- Bounded deterministic continuation summaries derived only from canonical session history.
- Suspend/resume integration proving prompt continuity without raw transcript replay.

## Out of Scope

- Public `StudyTool` manifests/registry, `grounding.ask` external-agent transport, CLI/export, web/API/UI, model-authored summaries, semantic entailment judges, retries of external model calls, provider-specific behavior, or product work.
- A canonical commit performed inside the current generic ToolStep executor.

## Session State Model

`SessionStatus`: `active | suspended | ended`.

Canonical entities:

- `StudySessionRecord`: session/course identity, status, started/suspended/resumed/ended timestamps, ordered interaction IDs, run IDs, and current continuation summary.
- `InteractionRecord`: immutable human, assistant, or note content with timestamp; assistant records link an answer ID and run ID but never use an opaque provider snapshot.
- `AnswerRecord`: answer/interaction/question/run IDs, canonical `GroundedAnswer`, complete provenance snapshot, and idempotency fingerprint.
- `ContinuationSummaryV1`: schema version, through-interaction ID, interaction count, bounded recent turns, grounded points, unresolved notes, and canonical character count.

Identifiers are deterministic SHA-256-derived values from course/session/run/idempotency inputs where retry identity is required. Same identifier with different canonical content is a conflict.

## Typed Event Family

All schemas are version 1, exact-key decoded, require matching `DomainEvent.session_id`, trusted actor/correlation/timestamp envelopes, and reject unknown fields.

- `session.started`: `{session_id}`; creates one active session.
- `session.interaction_recorded`: `{interaction_id, kind: human|note, content}`; active session only.
- `session.answer_recorded`: `{answer_id, interaction_id, question_interaction_id, run_id, idempotency_key, command_fingerprint, answer, provenance}`; active session, existing human question, unique answer/interaction/run/idempotency identities.
- `session.continuation_summary_updated`: `{summary}`; must advance monotonically through an existing interaction and exactly match deterministic reduction of canonical history.
- `session.suspended`: `{}`; active to suspended.
- `session.resumed`: `{}`; suspended to active while preserving history/summary.
- `session.ended`: `{}`; active or suspended to terminal ended; no later writes.

Recording one grounded exchange appends the human question, answer/assistant interaction, and summary update in one `EventStore.append` transaction. No partial question survives a failed finalization.

## Provenance Contract

`AnswerProvenance` contains:

- ordered unique source revision/chunk/span commitments reconstructed from canonical citations;
- prompt ID/version and optional composition fingerprint/layer fingerprints;
- optional model provenance with adapter ID/version, model ID, response ID, run ID, and optional usage;
- retrieval strategy ID/version, query fingerprint, index version, and read-set fingerprint;
- ordered validator ID/version/outcome fingerprints;
- skill, playbook, prompt, model-adapter, state-contract, and tool-behavior pins;
- playbook run ID and event/reducer schema versions.

The assembler consumes only verified run output/checkpoint, trusted trace details, the canonical evidence envelope/receipt, and citation resolution. Model output cannot supply provenance.

Rules:

- `answered` and `conflicting_evidence` require one successful model invocation matching the adapter pin.
- Deterministic `insufficient_evidence` requires `model=None`, no prompt composition fingerprint, no citations/source commitments, one real retrieval receipt, and the executed evidence-sufficiency validator. It must not invent adapter/model/run response data.
- `failed` runs are never persisted as answers.
- Every cited source revision/span is re-resolved at commit and must match the validated answer and retrieval read set.

## Retrieval and Validator Receipts

- Extend the provider-neutral retrieval result/evidence envelope with explicit `strategy_id`, `strategy_version`, `index_version`, and deterministic read-set fingerprint. SQLite supplies these through the generic contract; session code never imports adapter constants.
- Evidence presented to the model may include these non-secret receipt fields, but the model cannot mutate them because the validator and finalizer consume the trusted tool output.
- Every validate/fallback execution trace records trusted validator ID/version, passed/disposition, and a canonical result fingerprint. These details are generated by the engine, not returned by validators as identity claims.

## Verified Run Recovery

Add a read-only engine/run inspection API that loads a checkpoint and returns a completed or semantically successful terminated result only after validating:

- definition fingerprint and exact run inputs;
- version pins and model adapter identity;
- read dependencies;
- trace sequence and checkpoint status/next-step consistency;
- output/trace immutability and schema decoding.

Recovery never re-executes external steps. A crash after run completion and before domain commit can therefore finalize the same run exactly once.

## Application Service

`SessionService` owns lifecycle commands and views. `GroundedSessionFinalizer` owns answer commit.

- `start`, `record_note`, `suspend`, `resume`, and `end` require a host-created `ExecutionContext` matching course/session ownership.
- `finalize_grounded_run` accepts the verified run record, exact pins/definition/inputs/read dependencies, and idempotency key; it assembles provenance, revalidates citations, builds the deterministic event batch, and appends once.
- Event IDs, answer ID, and assistant interaction ID are derived from course/session/run/idempotency identity.
- Same idempotency key/run and byte-equivalent canonical command returns the existing result.
- Same identity with different question/answer/provenance returns explicit idempotency conflict.
- On course sequence conflict, reread once: return existing exact result or a retryable sequence conflict. Never rerun the model.
- `StateWritePolicy` for `grounded_answer@1` declares exactly the session events the finalizer may emit; finalizer rejects any event outside the allow-list.

## Continuation Summary

Summary generation is deterministic code, not a model call:

- maximum four recent grounded exchanges;
- maximum 2,000 Unicode characters in canonical serialized learner/assistant excerpts;
- deterministic newest-preserving truncation and oldest-drop policy;
- answer entries include status, claim text, and unsupported note, not citations or source bytes;
- exact linkage to `through_interaction_id` and total interaction count;
- replay recomputes and verifies byte-identical summary content.

`session.get_context` returns the structured bounded summary and never the interaction array. Resume preserves the same summary until new canonical interactions advance it.

## Acceptance Criteria

- [x] Every canonical session/answer mutation is a typed event reduced atomically with the existing source stream.
- [x] Unknown fields, invalid envelopes, cross-course/session IDs, duplicate IDs, stale summaries, writes after end, and tampered provenance fail closed.
- [x] A supported/conflicting answer persists exact citations plus source/prompt/model/retrieval/validator/run provenance assembled from trusted records only.
- [x] Insufficient evidence persists without a model call or fabricated model/prompt-composition provenance.
- [x] Question, answer, assistant interaction, and summary update commit in one transaction; reducer failure rolls back all events/projection changes.
- [x] Retrying after a successful append returns the same answer without duplicate events; changed content under the same key conflicts.
- [x] A completed run can be recovered after process loss and finalized without repeating model/tool effects.
- [x] Suspend/resume passes only the bounded summary to the next prompt and never requires raw chat replay.
- [x] Projection deletion/rebuild over mixed source and session events yields byte-identical canonical state.
- [x] Session views read projections only and expose no mutation path or SQLite types.
- [x] `grounded_answer@1` declares the exact allowed session write events; adapters contain no session policy.
- [x] Default tests are offline and require no provider/API key/Tau/product application.
- [x] Unit, contract, integration, eval, Ruff, mypy, architecture, and diff gates pass.

## Verification

- Unit: strict event codecs, reducers, summary bounds, provenance assembler, run recovery, idempotency fingerprints.
- Contract: `SessionViewPort` and honest optional-model provenance invariants.
- Integration: supported/insufficient finalize, atomic rollback, crash recovery, concurrent retry, suspend/resume prompt context, mixed replay/rebuild.
- Architecture: no adapter/product imports in domain/ports/sessions; no SQLite constants in application/session code.

## Task Beads

- `session-event-kernel`: domain/provenance contracts, typed events, pure reducers, summary, registry, and session view.
- `trusted-run-receipts`: retrieval receipts, validator trace provenance, and verified completed-run recovery.
- `session-answer-finalizer`: lifecycle application service, provenance assembly, atomic idempotent finalization, suspend/resume and replay integration.
