# ADR-0011: Separate capability-gap observation from improvement authority

Date: 2026-07-16
Status: Accepted

## Context

A tutor will encounter learner needs that the installed harness cannot satisfy,
such as an unsupported material format or missing integration. Today it can
explain the limitation and perhaps use an already-authorized workaround, but the
observation is lost. Feeding repeated real limitations into the development
workflow could make the OSS harness improve from use rather than only from a
prewritten roadmap.

The reporting agent is still processing untrusted learner input. Letting it open
external tickets, assign roadmap priority, install converters, change code, or
start implementation would promote model output into product and engineering
authority. Storing product feedback in the per-course event stream would also
mix development operations with canonical learning history.

## Decision

1. Add an optional **Capability Gap Plane** owned by the embedding host. It is
   separate from the canonical study plane and management-plane authority.
2. Expose `report_capability_gap@1` as an agent-facing host tool backed by a
   provider-neutral application service and injected `FeatureGapSink`. It is not
   registered as an eighth StudyTool and does not alter capability manifests.
3. An MVP report contains only closed categories and structured identifiers:
   requested operation kind, safe target family, trusted operation/error receipt,
   contract-major fingerprints, impact kind, and bounded workaround status. It
   contains no free-form model or learner text. Raw material, file contents,
   paths, filenames, credentials, prompts, commands, and executable payloads are
   structurally inexpressible rather than heuristically redacted.
4. The tutor may attempt a workaround only through capabilities and tools that
   were already authorized by the host. A model may record only a closed
   workaround suggestion. `attempted_succeeded|attempted_failed` is derived
   exclusively from a host-trusted execution receipt supplied out of band. The reporting tool records the outcome;
   it never searches, converts, installs, executes, or acquires new authority.
5. The core derives report identity and `GapKeyV1` as domain-separated SHA-256
   over canonical JSON containing `gap_key_schema_version=1`, category,
   requested-operation kind, safe target kind, trusted limitation code, relevant
   contract identity, and contract major. Canonical bytes use sorted keys and
   fixed UTF-8 separators. It performs no LLM/fuzzy deduplication; an existing
   key with different canonical dimensions fails as `gap_key_collision`. The model
   cannot set ticket ID, priority, severity, assignee, milestone, implementation
   choice, or external issue body.
6. Reports are local operational records by default. Repeated observations are
   aggregated without duplicating raw text. They are not learner facts, mastery
   evidence, course events, or prompt memory.
7. A credential-free, redacted outbox bundle is the only portable boundary.
   Export off-device is explicit and host-controlled; the core performs no
   network or GitHub operation.
8. The Flywheel may import an outbox bundle through a strict adapter, reproduce
   each gap with offline fixtures where possible, and deduplicate it against
   active work. It creates one immutable technical proposal per gap key or
   explicitly equivalent cohort; independent gaps never share authorization.
   Each proposal contains options, recommendation, draft ADR/spec, and draft bead graph.
9. Each proposal becomes one structured maintainer decision request. Until it is
   accepted, no public issue, approved spec, implementation goal, dependency,
   code mutation, or publication is created.
10. One acceptance may authorize promotion of that one already-visible proposal to
    approved spec/beads and an implementation goal. Normal worker, test,
    semantic-review, and publication gates still apply. Rejection, deferral, and
    duplicate resolution are durable outcomes.
11. Optional GitHub issue synchronization is a later outbound adapter and may
    occur only after acceptance. Flywheel artifacts remain the canonical
    engineering workflow.
12. The harness core never calls Flywheel. It writes a strict redacted bundle to
    an injected `GapOutboxTransport`. The default OSS transport is local. A
    hosted deployment may install an outbound adapter that delivers the same
    bytes to a private Improvement Intake inbox using at-least-once delivery,
    idempotency over `(authenticated_sender_scope, bundle_fingerprint)`, service authentication, bounded retries, and
    acknowledgement only after durable inbox persistence.
13. A private factory worker consumes the inbox and invokes the normal devkit
    importer. The public tutor cannot address Flywheel runs, decision requests,
    repositories, or implementation goals. Invalid bundles are quarantined;
    transport failure leaves the local outbox pending and does not block study.
    Sender scope is operational inbox metadata used only for delivery identity
    and authorization; it is not forwarded into Flywheel proposal evidence.
    The inbox derives `delivery_import_id` as a domain-separated hash of sender
    scope and bundle fingerprint and supplies it to the devkit only as trusted
    idempotency context. Each delivery contributes at most once; contributions
    from different deliveries may converge under the normal `GapKeyV1` aggregate.
    Neither sender scope nor delivery ID enters proposal evidence.

## Consequences

- The harness becomes self-observing and improvement-proposing, not
  self-modifying.
- Real unsupported needs can accumulate into an auditable backlog with low
  learner and maintainer friction.
- The exact seven StudyTools, event-sourced course history, skills/playbooks,
  model adapters, and provider neutrality remain intact.
- Hosts must decide whether and when local reports are exported.
- Hosted deployments must provide and operate their own authenticated intake
  transport/inbox; this technical adapter remains outside the provider-neutral
  core.
- Maintainer attention remains the scarce authority; deduplication, thresholds,
  and consolidated decision requests prevent one prompt from becoming one task.

## Alternatives Considered

- Let the tutor open GitHub issues directly: rejected because it leaks untrusted
  text and grants external mutation authority.
- Store gaps as course events: rejected because product backlog state is not
  learning history.
- Add an eighth StudyTool: rejected because reporting is a host observability
  concern and would break the closed public study-tool contract.
- Automatically implement every observed gap: rejected because frequency does
  not establish correctness, priority, safety, or architectural fit.
- Keep feedback entirely manual: rejected because repeated real limitations and
  workaround evidence would be lost.
