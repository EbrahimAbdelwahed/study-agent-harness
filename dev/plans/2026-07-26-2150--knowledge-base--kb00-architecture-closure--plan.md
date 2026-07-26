# Plan: KB-00 architecture closure

Date: 2026-07-26 21:50
Area: knowledge-base

## Goal

Resolve the identity, compatibility, conformance, replay, and ownership
contradictions that block every KB v0.2 runtime schema.

## Scope

- In scope: ADR-0014, parent-spec corrections, dependency corrections, v0.1
  migration/removal conditions, the reusable core worker profile, and KB-01
  worker briefs.
- Out of scope: runtime schemas, external dependencies, OCR, model/vector
  providers, UI, tutor behavior, and hosted transport.

## Approach

1. Map current v0.1 ingestion, citation, retrieval, event, export, and CLI
   consumers.
2. Separate occurrence, lineage, cache, projection, and citation identities.
3. Pin versioned compatibility and the runtime bridge removal bead.
4. Separate admission failures from structural conformance.
5. Correct replay promises and dependency edges.
6. Run an independent architecture audit before marking KB-00 done.

## Risks

- A supposedly stable unit identity could collapse duplicate placements.
- A compatibility layer could become an indefinite second retrieval model.
- Derived cache behavior could acquire canonical authority.

## Verification

- Read-only mapping against current v0.1 owners and fixtures.
- Independent architect and architecture-auditor review.
- `git diff --check`.
