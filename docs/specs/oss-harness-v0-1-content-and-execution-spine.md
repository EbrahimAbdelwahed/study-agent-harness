# Feature Spec: OSS Harness v0.1 Content and Execution Spine

Status: Implemented
Owner: Ebrahim / Codex orchestrator
Date: 2026-07-10
Run ID: `20260710-oss-harness-v01-batch2`
Parent spec: `docs/specs/oss-study-agent-harness-v0-1.md`

Implementation review: [`../reviews/20260710-oss-harness-v01-batch2.md`](../reviews/20260710-oss-harness-v01-batch2.md)

## Goal

Implement the two dependency-ready foundations after the approved contract/state slice: an immutable local content-addressed blob store and a deterministic sequential playbook engine that executes the accepted v0.1 AST through injected provider-neutral ports.

## Problem

The current package defines `BlobStore`, skills, playbooks, checkpoints, data bindings, capability negotiation, and model transport contracts, but has no content persistence implementation and cannot execute a playbook. Text ingestion and grounded-answer work therefore have no durable blob boundary or reusable execution mechanism.

## In Scope

- A filesystem `BlobStore` adapter using SHA-256 content addresses.
- Idempotent writes, atomic publication, integrity verification on read, safe path derivation, and immutable stored bytes.
- A sequential playbook engine for the trusted `tool`, `model`, `dialogue`, and `validate` AST.
- Provider-neutral resolution of run-input and previous-output bindings.
- Preflight of engine compatibility, model capabilities, tool behavior versions, and version pins before effects.
- Injected tool and validator executors; injected `ModelPort`; no provider SDK.
- `dialogue` suspension with a persisted checkpoint and explicit resume input.
- Checkpoint compatibility/read-dependency validation and deterministic trace records.
- Validation termination semantics, including structured early termination without executing later steps.
- Focused fake/scripted executors and deterministic unit/integration tests.

## Out of Scope

- Text/Markdown normalization and chunking.
- Source-document events or source manifest projections.
- Retrieval, FTS, grounding prompts, grounded-answer skill content, sessions, CLI, or export.
- Real model/provider adapters, Tau adoption, network calls, retries, loops, conditions, parallel branches, transactional groups, or untrusted playbooks.
- Product/UI work, Sbobby changes, Postgres, sync, auth, and hosted services.

## Domain Model

- `BlobRef`: existing immutable reference returned by the filesystem adapter.
- `PlaybookRunResult`: provider-neutral completed, suspended, terminated, or failed execution outcome.
- `PlaybookCheckpoint`: existing pinned operational state; the engine must persist it through `RunStore` without treating it as canonical domain state.
- `StepTrace`: existing deterministic trace vocabulary extended only when required to describe engine behavior without provider leakage.

## API / Interface Contract

- `FilesystemBlobStore` implements the existing `BlobStore` protocol.
- `PlaybookEngine` receives registries/executors through constructor injection and executes a validated `PlaybookDefinition` plus immutable run inputs and `VersionPins`.
- Tool and validator executor protocols use JSON-compatible inputs/outputs and declared behavior versions.
- Model execution uses only `ModelPort`; prompt composition remains outside provider adapters.
- Run/checkpoint persistence uses `RunStore`; a deterministic in-memory reference implementation may be used for tests but is not canonical domain state.

## Prompt Behavior

- No production prompt text changes in this batch.
- `ModelStep.prompt_bindings` are resolved into canonical prompt input data, not provider-specific messages or branches.
- Scripted model fixtures prove the engine passes the same canonical request independent of provider identity.

## RAG / Source Grounding

- No retrieval implementation in this batch.
- Engine tests use synthetic evidence-like JSON only to prove binding and validation termination.
- No claim of citation correctness is introduced.

## Risks

- Accidentally building a generic workflow framework instead of the minimal accepted study procedure executor.
- Performing tool/model effects before capability, tool-version, pin, or checkpoint validation.
- Treating checkpoints as canonical domain state.
- Allowing mutable binding results or provider-specific execution branches.
- File replacement, symlink, or traversal behavior weakening content immutability.

## Acceptance Criteria

- [x] Writing the same bytes twice returns the same `BlobRef` and creates one immutable content object.
- [x] Reading verifies size and SHA-256 and fails explicitly on corruption or missing content.
- [x] Blob paths are derived only from validated lowercase SHA-256 digests and cannot escape the configured root.
- [x] Blob publication is atomic and never overwrites different bytes at an existing digest path.
- [x] A complete sequential playbook executes tool, model, validate, and commit-like tool steps with correct binding resolution.
- [x] A validator can terminate early with structured output and no later model/tool call occurs.
- [x] A dialogue step suspends, persists a pinned checkpoint, and resumes only with compatible pins and declared input.
- [x] Unsupported model capabilities or tool behavior versions fail during preflight before any executor is called.
- [x] Incompatible/stale checkpoints fail explicitly before resume effects.
- [x] Engine traces and outputs are deeply immutable and provider-neutral.
- [x] Default tests require no network, API key, provider SDK, or Tau.
- [x] Full pytest, Ruff, mypy, import-boundary, and independent semantic review gates pass.

## Verification

- Unit: digest/path derivation, idempotency, corruption, binding resolution, preflight, termination, checkpoint compatibility.
- Integration: temporary filesystem CAS; complete and suspended/resumed scripted playbook runs.
- Evals: deterministic scripted executors only; no model-quality eval in this batch.
- Manual: inspect stored content layout and one serialized checkpoint/trace fixture.

## Open Questions

- none

## Task Beads

- `local-content-store`: implement immutable filesystem content-addressed storage.
- `minimal-playbook-engine`: execute the accepted sequential playbook AST through injected ports.
