# Agent-managed harness lifecycle

Status: Shipped in 0.2.0

## Purpose

The lifecycle management plane lets an external agent discover, initialize,
populate, inspect, and recover a local study harness without becoming part of
the study domain. Desired intent is useful automation input, but it is not
canonical state and cannot acquire authority merely because a model or manifest
proposed it.

This separation preserves the central architecture: domain events remain the
study record, skills and playbooks remain the behaviour layer, and model
adapters remain technical transports. The accepted rationale is also recorded
in [`ADR-0003`](../../../docs/decisions/ADR-0003--agent-operated-management-plane.md).

## Why the boundary has this shape

Setup commands could have been added to the model-facing StudyTools, but doing
so would let untrusted model arguments select repositories, identities, and
write authority. Instead, the embedding host supplies authority out of band and
the management plane invokes the existing application-service owners. The exact
seven StudyTools therefore stay focused on study behaviour.

A manifest could also have been treated as the desired database, or applied as
one repository-wide transaction. Neither is honest: course streams, immutable
blobs, and the discardable retrieval index do not share a global transaction.
Apply is intentionally atomic only at each existing owner boundary and reports
partial, degraded, and conflicting work explicitly.

## Invariants

- The append-only event stream is the only canonical study state. Manifests,
  plans, receipts, indexes, and checkpoints are operational evidence.
- Lifecycle intent is local, bounded, add-only, offline, and non-executable. It
  cannot select authority, skills, playbooks, prompts, capabilities, credential
  values, deletion, remote acquisition, or config migration.
- `LifecycleAuthority` is trusted host input. The reference CLI fixes the
  SERVICE principal and derives correlation from the authorized plan; manifest
  fields cannot override either.
- Planning is pure over validated intent, immutable source snapshots, and
  descriptor-bound observation. Applying a plan requires its exact fingerprint
  and revalidates each action against fresh observed state; course and source
  stream writes additionally use expected-sequence/CAS semantics.
- Recovery starts from evidence: status, a fresh plan, then apply of that fresh
  fingerprint. An old fingerprint is never a blanket replay authorization.
- Retrieval is discardable. Canonical source work may succeed while index work
  is reported degraded; repair rebuilds from the event stream and blobs.
- Historical source content remains immutable. Returning from revision B to A
  records an explicit selection event instead of duplicating or rewriting A.
- Skills and playbooks continue to own study behaviour. Provider adapters and
  lifecycle adapters remain technical composition only.

## Filesystem and concurrency model

Manifest and source paths are resolved beneath explicit trusted roots with
no-follow, stable-identity checks. The reference CLI additionally pins the
retained `state` directory while mutating SQLite, opens existing database names
with no-follow semantics, and proves the live SQLite file descriptor matches
the inspected inode before the first write. Persistent replacement of a
repository, config, database, or source input fails closed. Writable SQLite
files are also protected against A→B→A replacement before mutation.

The CLI composition is deliberately serial. Its descriptor pin uses a
process-global working-directory scope, restored on every exit. An embedding
host that performs concurrent relative-path I/O must supply a different
`LifecycleRuntime` isolation strategy, such as a dedicated subprocess; this is
not a concurrency guarantee of the model-agnostic core.

## Divergences discovered while building

An absent repository converges in two plans, not one: the first plan creates
only the verified operational layout, and a fresh plan populates canonical
state. This avoids carrying an unverified pathname across initialization.

Source metadata became revision-bearing so declarative drift has a canonical
meaning. Legacy revision identities remain replayable. Re-selecting a
historical revision required a dedicated event because treating any historical
match as idempotent left the current revision divergent.

Descriptor-bound observation was insufficient for writable SQLite by itself:
Python's standard `sqlite3` API still opens a pathname. The reference adapter
therefore combines a retained directory, secure file creation, SQLite no-follow
mode, and live descriptor identity proof. Pre/post pathname checks alone were
rejected because they detected replacement only after a possible external
write.

## Pointers to the shipped contracts

- Lifecycle values and fingerprints: `study_agent.lifecycle.contracts`
- Pure reconciliation: `study_agent.lifecycle.planner`
- Per-action apply and receipts: `study_agent.lifecycle.service`
- Trusted reference composition: `study_agent.cli.lifecycle`
- Repository/source safety: `study_agent.adapters.filesystem`
- SQLite identity guard: `study_agent.adapters.sqlite.event_store`
- Agent workflow: `study_agent.operator_skill`

The normative manifest example remains in [`fixtures/`](fixtures/). Behaviour
and recovery are pinned by the lifecycle contract, CLI manifest, ingestion
replay, filesystem adversarial, and recovery-matrix tests under `tests/`.

## Deliberately deferred

Destructive reconciliation, remote sources, dynamic behaviours, configuration
migration, repository-wide transactions, and a concurrent in-process reference
runtime require separate decisions. They are not implied by version 0.2.0.
