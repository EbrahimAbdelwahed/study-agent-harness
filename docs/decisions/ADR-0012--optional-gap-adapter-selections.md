# ADR-0012: Select bounded reference adapters for deferred gap lanes

Date: 2026-07-21
Status: Proposed

## Context

GAP-04B, GAP-05D/GAP-07B, and GAP-08 intentionally deferred concrete adapter
selection. Closing them without a named dependency, effect boundary, and threat
model would turn scripted ports into false production claims. The reference
implementations should remain optional, offline-testable, and narrower than the
provider-neutral contracts they demonstrate.

## Decision

1. GAP-04B uses a standard-library HTML-to-plain-Markdown adapter. It accepts
   only a host-captured immutable `text/html` snapshot below configured byte and
   expansion limits, never resolves links or executes active content, and emits
   a UTF-8 `.md` derivative with exact source checksum, converter version, and a
   mandatory lossy-conversion warning. It is a temporary workaround, not native
   HTML ingestion or a general document converter.
2. GAP-05D uses an authenticated shared-volume inbox as the OSS hosted-reference
   transport. Separately deployed tutor and factory processes share only a
   private durable inbox volume. The sender writes exact GAP-05A bundle bytes
   plus a separate HMAC-SHA256 delivery envelope using a key read from a named
   environment variable. Descriptor-relative no-follow writes, size bounds,
   fsync plus atomic rename, sender-scope binding, and inbox-side verification
   provide at-least-once durable delivery without adding an HTTP/cloud
   dependency. Deployments without a private shared volume supply another
   `GapOutboxTransport` adapter.
3. GAP-07B consumes that inbox through the provider-neutral consumer port. It
   validates bundle and delivery identities again, calls the devkit importer,
   and acknowledges only after importer persistence.
4. GAP-08 uses an optional GitHub REST issue adapter over an injected HTTP
   client. The adapter reads a token from a named environment variable, accepts
   only accepted immutable proposal views, emits a closed redacted issue body,
   and uses a proposal-fingerprint marker for idempotency/tamper detection.
   Default tests inject a scripted client and perform no network. Live tests are
   opt-in; issue creation, mutation, and resolution feedback require explicit
   maintainer actions. Verified release/capability evidence—not issue state—owns
   local resolution.

## Consequences

- All deferred lanes receive concrete, testable adapter choices without adding
  dependencies to the base harness.
- The shared-volume adapter is a reference deployment pattern, not a claim that
  every hosted topology has a shared filesystem.
- HTML conversion deliberately loses layout, images, scripts, forms, and
  styling; provenance and the warning prevent it from masquerading as native
  support.
- GitHub remains an optional collaboration sink and never becomes canonical
  workflow state or tutor authority.

## Security and Verification Gates

- Hostile HTML, entity/expansion limits, symlink/race/rebinding, derivative
  provenance, and failure-preserves-report tests.
- Wrong-key/sender replay, tamper, oversize, duplicate/crash boundaries,
  durable-before-ack, quarantine, permissions, and secret-scan tests.
- GitHub auth/rate/permission/network failure, marker collision/tamper,
  redaction, explicit-action, accepted-only, and release-evidence tests.
- Architecture gates keep converter, inbox authentication, HTTP, GitHub, and
  devkit imports outside canonical course, skill/playbook, and core feedback
  owners.

## Alternatives Considered

- PDF/OCR/audio as the first converter: rejected for large native/system or ML
  dependencies and materially different quality/sandbox risks.
- A mandatory hosted HTTP service: rejected because the OSS repository has no
  selected deployment/auth platform and the core must remain transport-neutral.
- GitHub CLI subprocesses: rejected because shell/process authority is broader
  and harder to audit than a bounded HTTP client port.
