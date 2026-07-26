# Plan: KB v0.2 bead decomposition

Date: 2026-07-26 15:06
Area: knowledge-base

## Goal

Turn the proposed KB v0.2 retrieval architecture into dependency-ordered,
independently verifiable implementation beads without changing runtime code.

## Scope

- In scope: architecture closure, canonical substrate and citation state,
  structural projections, offline retrieval, connectors, incrementality,
  figures, optional semantic adapters, and release evals.
- Out of scope: implementation, dependency selection, product UI, tutor policy,
  transport bindings, and approval of the proposed parent spec.

## Approach

1. Map the parent milestones to existing v0.1 owners and public seams.
2. Isolate unresolved architecture contradictions in a blocking decision bead.
3. Split work at public API, event/schema, persistence, algorithm, and external
   adapter boundaries.
4. Give every bead explicit dependencies, risk, acceptance criteria, and
   verification.
5. Audit the graph for one-owner architecture and dependency-ready pickup.

## Risks

- Treating broad M1–M9 milestones as implementation-sized tasks.
- Duplicating existing ingestion, citation, retrieval, or blob-store owners.
- Allowing optional model/vector/vision behavior into the offline lexical trunk.
- Implementing unstable identity or replay semantics before their contradiction
  is resolved.

## Verification

- Inspect every parent-spec section and milestone for bead coverage.
- Check every dependency target exists and the graph is acyclic.
- Check the diff contains documentation only.
