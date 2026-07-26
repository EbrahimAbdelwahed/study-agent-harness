# Worker Profile: knowledge-base-core-worker

Generated: 2026-07-26
Source task: `specs/kb-v0-2/README.md`

## Reuse Trigger

Use this worker for one bounded, provider-free KB v0.2 bead involving canonical
evidence, pure structural algorithms, versioned public contracts, replayable
projections, or the permanent offline lexical path.

## Mandate

Implement one approved KB tracer bullet without redesigning identities,
duplicating v0.1 owners, introducing provider behavior, or allowing derived and
operational state to become canonical.

## Scope

In scope:

- The exact production or test files allowlisted by the assigned worker brief.
- Strict typed values, canonical codecs, deterministic reducers/projections,
  pure algorithms, and offline integration evidence owned by that bead.
- Versioned v0.2 successors and explicitly bounded v0.1 migration bridges.

Out of scope:

- Architecture, identity, migration, provider, dependency, prompt, product, or
  authority decisions not already accepted in ADR-0014 and the assigned bead.
- OCR, vision, embeddings, reranking, model projectors, hosted services, UI,
  tutoring policy, scheduling, or changes to skill/playbook behavior.
- Unrelated refactors or compatibility wrappers without a named removal bead.

## Required Context

Read first:

- `docs/decisions/ADR-0014--kb-v02-identity-compatibility-and-replay.md`
- `docs/specs/kb-v0-2-retrieval-architecture.md`
- `specs/kb-v0-2/README.md`
- the assigned bead and worker brief
- current v0.1 owner modules and applicable `AGENTS.md`

Current-doc research is not needed for the provider-free core. Stop and request
a separate dependency/provider decision if the bead reaches a fast-moving
external library or service.

## Allowed Files

Edit only paths explicitly allowlisted by the worker brief. Inspect relevant
domain, ingestion, state, ports, retrieval, adapters, compatibility fixtures,
ADRs, and tests. Do not edit files reserved by another worker.

## Forbidden Decisions

Stop and report before:

- changing any ADR-0014 identity or collision domain;
- mutating a v0.1 persisted contract in place;
- adding a canonical cache/invalidation event;
- adding a dependency, provider, model, network, subprocess, or filesystem
  authority;
- moving behavior from skills/playbooks into an adapter;
- accepting caller-authored hashes, provenance, authority, or final IDs.

## Quality Gates

- Canonical bytes and events are immutable; projections/indexes rebuild.
- Every durable codec is closed, bounded, canonical, and rejects bool-as-int,
  extra/missing fields, forged hashes, and cross-owner references.
- Derived text is non-citable and operational state has no mutation authority.
- Default behavior is offline, credential-free, deterministic, and
  provider/model/agent agnostic.
- Focused tests, Ruff, strict mypy, relevant architecture/replay tests, full
  suite at milestone boundaries, build/clean-wheel gates, and
  `git diff --check` pass.

## Report Format

Return files changed, contracts implemented, invariants preserved, exact
verification commands/results, compatibility impact, unresolved risks, and the
recommended next bead. Do not delegate or commit unless the brief explicitly
requires it.
