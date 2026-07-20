# Task Bead: GAP-05D hosted private intake transport

Status: Scope approved — blocked on GAP-05A and deployment/auth adapter selection
Priority: P1
Type: tracer-bullet
Depends On: GAP-05A

## Outcome

A hosted tutor deployment can deliver exact redacted outbox bundles to a private
durable Improvement Intake inbox and expose a typed consumer port, without
exposing Flywheel or GitHub to the tutor runtime.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Real production delivery between separately deployed tutor and factory.

## Grilling Evidence

- Session/artifact: accepted ADR-0011 production-transport amendment.
- Decision state: transport scope approved 2026-07-18; concrete deployment/auth
  adapter must still be selected before dispatch.
- ADR/glossary changes: private intake inbox and delivery receipt.

## Worker Profile

reuse `architect` then `implementer`; require `security-reviewer`

Rationale: authenticated cross-deployment boundary with privacy, replay, and
availability implications.

## Context

GitHub is a collaboration tracker, not a secure runtime transport. The tutor
delivers a bounded envelope to a private factory inbox; Flywheel remains behind
that inbox and consumes only through the devkit importer.

## What To Do

- Define `GapOutboxTransport` and `GapDeliveryReceipt` contracts independently of
  HTTP, queues, or cloud vendors.
- Provide the hosted adapter selected by deployment configuration; it sends exact
  bundle bytes with service authentication and idempotency over
  `(authenticated_sender_scope, bundle_fingerprint)` so identical bytes from
  different deployments remain independent observations.
- Persist to an inbox before acknowledging. Use at-least-once delivery, bounded
  retry/backoff, duplicate convergence, quarantine for invalid bundles, and
  operator-visible failure without blocking the study session.
- Expose durable inbox records through a typed consumer/acknowledgement port;
  integration with the GAP-05B importer belongs to GAP-07B. Never expose
  Flywheel commands, run IDs, repository coordinates, or decision APIs to the tutor.
- Derive `delivery_import_id` from authenticated sender scope plus bundle
  fingerprint and expose it only as trusted consumer/import idempotency context.

## Acceptance Criteria

- [ ] Network loss before acknowledgement leaves the local outbox pending;
  retry delivers one durable inbox record.
- [ ] Duplicate deliveries converge only within the same authenticated sender
  scope and bundle fingerprint; identical bytes from distinct sender scopes
  remain distinct inbox observations.
- [ ] Authentication failure, tamper, oversize, unknown schema, and replay from
  the wrong deployment fail or quarantine without reaching Flywheel.
- [ ] The delivery payload is byte-identical to GAP-05A and contains no learner
  text, path, filename, credential, or principal identity.
- [ ] Sender scope remains operational inbox metadata and is never copied into
  the portable bundle or downstream Flywheel evidence; the derived delivery ID
  is likewise excluded from proposal evidence.
- [ ] Core packages import no HTTP/queue/cloud/devkit/Flywheel dependency.
- [ ] Study continues when intake is unavailable.

## Verification

- Scripted authenticated transport/inbox, loss-before/after-durable-write,
  duplicate, retry/backoff, quarantine, secret scan, dependency firewall, and
  full offline defaults; live-network tests remain opt-in.

## Out Of Scope

- Public endpoint, GitHub issue creation, proposal generation, implementation,
  or choosing a cloud vendor in the core contract.
