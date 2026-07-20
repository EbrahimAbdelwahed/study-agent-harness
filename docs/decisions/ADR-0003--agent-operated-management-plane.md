# ADR-0003: Agent-operated management intent does not own domain state

Date: 2026-07-13
Status: Accepted

## Context

The v0.1 harness exposes trusted CLI setup operations and seven schema-bounded
study tools, but it does not yet provide one discoverable, retry-safe lifecycle
for an external agent. Adding setup as model-facing tools would mix authority
with model-proposed arguments. Treating a desired-state manifest as canonical
would conflict with the accepted event-sourced state model.

## Decision

Introduce a separate, host-trusted management plane. Version 0.1.1 makes the
existing primitives machine-discoverable and crash-retry-safe. Version 0.2 adds
an optional local desired-state manifest with `validate`, `plan`, `status`, and
`apply` operations.

The manifest is operational intent. Reconciliation invokes the existing course,
source, and session application services, and only their domain events become
canonical. No generic `manifest.applied` domain event is emitted. Plans and
receipts are operational evidence and may be regenerated.

The embedding host supplies a trusted `LifecycleAuthority` containing principal
kind, principal ID, and correlation identity. Declarative CLI apply uses the
fixed SERVICE principal `study-agent-cli` and derives a stable correlation root
from the expected plan fingerprint. Per-action idempotency identities are
derived from that trusted plan/action identity. The manifest cannot set or
override any of these fields. Existing procedural v0.1 commands retain their
local-user actor semantics for compatibility; the operator skill documents that
they execute under the authority of the local user who launched the agent.

The exact seven StudyTools remain the model-facing study plane. Repository
initialization, population, course discovery, and explicit session setup do not
become additional StudyTools. The trusted host continues to create execution
context and idempotency identities separately from model arguments.

Manifest v1 is local, add-only, offline, strict, and non-executable. It cannot
load plugins, select study behavior, contain credential values, acquire remote
sources, or request authority.

## Consequences

- External agents gain a deterministic setup and reconciliation surface without
  adopting an agent framework or model-specific adapter.
- Existing event schemas, repository config schema, procedural CLI commands,
  and StudyTool fingerprints remain compatible.
- Apply can partially converge before a failure; recovery is an idempotent rerun,
  not a fabricated cross-course transaction.
- Optimistic concurrency is checked per action using the observed course
  high-water and existing event-store sequence conflict. There is no claimed
  global repository lock: procedural and declarative mutations share service/CAS
  semantics rather than a lock that only one entry point observes.
- Filesystem manifest/source loading becomes a security-critical adapter with
  explicit traversal, symlink, size, race, and secret-handling tests.
- The reference CLI mutation adapter is serial: it pins the inspected SQLite
  owner through a process-global working-directory scope and verifies the live
  database descriptor before writing. Concurrent embedding hosts must provide
  their own isolated `LifecycleRuntime`, rather than reusing this CLI seam
  alongside unrelated relative-path I/O.
- Remote sources, destructive reconciliation, dynamic skills, and config
  migration require separate future decisions.

## Alternatives Considered

- Add setup/population StudyTools: rejected because model-facing arguments must
  not create their own authority and because v0.1 promises an exact closed set.
- Build a mandatory MCP/HTTP control plane: rejected because it couples the core
  to transport before a real consumer requires it.
- Make the manifest canonical: rejected because replayable domain events are the
  accepted source of truth.
- Keep only procedural CLI commands: rejected because multi-step population,
  drift inspection, and lost-output recovery remain unnecessarily brittle for
  automation clients.
- Apply the whole manifest transactionally: rejected because independent course
  streams, blob persistence, and discardable indexing do not share an honest
  global transaction boundary.
