# ADR-0001: Publish the study-agent harness as an OSS core

Date: 2026-06-29
Status: Accepted

## Context

The project could combine a reusable study-agent foundation with a hosted or
commercial product. Doing both at once would couple core contracts to product
delivery concerns and make the open-source contribution harder to evaluate and
reuse.

## Decision

Build and publish a provider-neutral study-agent harness. A hosted platform is
outside this project's scope.

The harness may contain typed domain, model, retrieval, tool, event, session,
and extension contracts; versioned study procedures; local adapters; evaluation
fixtures; documentation; examples; and a reference CLI. Persistence and
execution remain behind ports so downstream applications can provide different
implementations.

The harness does not contain a product shell, authentication, organizations,
billing, subscriptions, multi-tenant SaaS infrastructure, growth features, or
hosted operations.

## Consequences

- Architecture is optimized for portability, contributor experience, and
  inspectable public contracts.
- The reference CLI proves an end-to-end composition without becoming a product
  interface.
- Product applications may consume the harness but do not define its core.

## Alternatives considered

- OSS core and commercial platform in one release: rejected because it expands
  the scope and couples unrelated concerns.
- Hosted application only: rejected because it weakens reuse and the intended
  open-source contribution.
