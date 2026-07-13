# ADR-0002: Use event-sourced state and model-independent skills and playbooks

Date: 2026-07-10
Status: Accepted

## Context

The harness needs durable, inspectable study state and reusable study behaviour.
Mutable canonical tables with an audit log would make replay secondary. Putting
study procedures in model adapters would require behavioural forks whenever a
model or provider changes.

Provider APIs still need protocol translation. The objective is not to remove
integration code; it is to keep provider- and model-specific study logic out of
that code.

## Decision

### State

- The per-course append-only domain event stream is canonical.
- Every canonical mutation appends schema-versioned events with trusted actor,
  causation, correlation, and clock metadata.
- The reference SQLite adapter is single-writer per course and assigns a
  monotonic course sequence.
- Event append and synchronous projection updates share one transaction.
- Projections are rebuildable read models, not independent authorities.
- Identical event schemas and reducer versions produce byte-identical canonical
  projection state on replay.
- Snapshots and retrieval indexes are discardable accelerators.
- Blobs are immutable and content-addressed; events refer to their hashes.
- Playbook checkpoints, model traces, and retrieval diagnostics are operational
  state. Domain-relevant run transitions still emit events.

### Skills and playbooks

- A skill is a versioned capability package containing schemas, layered prompts,
  policies, requirements, fallbacks, validators, known failure modes, a playbook
  reference, and evaluation fixtures.
- A playbook is the model-independent execution procedure for a skill.
- The v0.1 playbook AST permits trusted sequential tool, model, dialogue, and
  validation steps with pinned checkpoints and suspend/resume.
- The engine owns order, state reads, validation, checkpointing, retries, and
  domain commits.
- Model selection uses capability negotiation. Portable fallbacks are declared
  by the skill.
- Model and provider adapters translate canonical requests, tool calls, stream
  events, usage, cancellation, authentication, and responses only.
- Adapters do not own study prompts, pedagogical or retrieval policy, grading,
  authority, or domain transitions.
- Skills and playbooks do not branch on provider or model names.

### Initial proof

The first built-in capability is `grounded_answer@1`, executed by
`grounded_answer_flow@1`. It must run unchanged through deterministic and real
compatible model adapters, commit only validated events, retain version pins,
and satisfy replay and adapter-conformance tests.

## Consequences

- The first release carries more foundational work than a CRUD-plus-prompt
  prototype.
- Provenance, replay, longitudinal evaluation, and future proposal workflows
  share one semantic substrate.
- Model experiments vary adapters and configuration while skill and playbook
  versions stay fixed.
- The initial AST remains deliberately constrained; loops, parallel branches,
  untrusted packages, and marketplace concerns require later decisions.

## Alternatives considered

- Mutable canonical tables plus audit records: rejected because replay semantics
  could be incomplete or lossy.
- Defer playbooks: rejected because model-specific behaviour would accumulate in
  the first grounded-answer implementation.
- Eliminate adapters through prompts: rejected because transports,
  authentication, streaming, cancellation, and tool-call encodings differ.
- Adopt a full workflow DSL immediately: rejected as unproven complexity.
