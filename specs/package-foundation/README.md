# Harness Package Foundation

Status: Implementation in progress — PF-01 through PF-04 closed

Last updated: 2026-08-09

## Next Agent Prompt

Start with dependency-ready PF-05 and PF-06 on the approved storage contract
kit. Read
`CONTEXT.md`, `CONTEXT-MAP.md`, this README, and the selected slice before
editing. Implement one slice at a time, keep the public contracts below
frozen, run the slice verification, and update this section before ending your
pass.

Current pickup: PF-05 Sources/citations and PF-06 Capabilities.

Evidence ledger:

- PF-01 closed at `7dad4d5`, with independent import-safety coverage at
  `6cac1e2` and approved review fixes at `0803eb7`. Python 3.12/3.13 focused
  tests, Ruff, mypy, import-isolation, and Flywheel semantic review are green.
- PF-02 closed through `d2e2078`, `e9d10c46`, and `070ac25c`. The final
  object-capability authority gate, bounded strict-JSON failures, exhaustive
  translation, Python 3.12/3.13 focused tests, integrations, Ruff, mypy, and
  independent adversarial semantic review are green.
- PF-03 is closed through `3eb81d6`, `97204e5`, `9617b6b`, and `101f9a0`:
  one SQLite event
  table accepts legacy and envelope bytes, `EventRegistry.prepare` resolves
  current schemas and upcasts before reduction, and the curated storage/runtime
  facades expose the approved seam. Python 3.12/3.13 focused tests, 654 broader
  tests, full strict mypy, mixed public/legacy replay-export probes, and final
  independent semantic review are green.
- PF-04 is closed through `5512fbb`, `8397b50`, and `361a638`: six public
  provider-neutral ports, keyed envelope writes, private legacy compatibility,
  typed blob/CAS/read-only outcomes, cross-adapter replay, and concurrent CAS
  coverage pass Python 3.12/3.13, strict mypy, and independent review.

Active warnings:

- This specification owns package stabilization only. Job orchestration,
  workers, web evidence, sealed verification, and Decision Trace are later
  runtime work and must not enter these slices.
- The package base must remain standard-library-only. Provider, FSRS,
  filesystem, telemetry, and specialist integrations stay behind optional
  adapters or extras.
- Cardine is a downstream consumer. Harness code and this specification must
  not import or name Cardine product modules, auth, UI, or deployment code.

Implementation checklist:

- [x] [PF-01 — Public manifest](slices/PF-01-public-manifest.md)
- [x] [PF-02 — Failures and authority](slices/PF-02-failures-authority.md)
- [x] [PF-03 — Events, upcasting, and module](slices/PF-03-events-upcasting-module.md)
- [x] [PF-04 — Storage contract kit](slices/PF-04-storage-contract-kit.md)
- [ ] [PF-05 — Sources and citations](slices/PF-05-sources-citations.md)
- [ ] [PF-06 — Capabilities](slices/PF-06-capabilities.md)
- [ ] [PF-07 — Artifacts, assessments, and recall](slices/PF-07-artifacts-assessments-recall.md)
- [ ] [PF-08 — Async-first runtime](slices/PF-08-runtime.md)
- [ ] [PF-09 — Distribution](slices/PF-09-distribution.md)
- [ ] [PF-10 — Release](slices/PF-10-release.md)
- [ ] [PF-11 — Stable facade promotion](slices/PF-11-stable-facade-promotion.md)

Before ending each implementation pass, update the status, current pickup,
warnings, and checklist above with the observed verification result. Do not
create beads from this folder; the implementation orchestrator will create
them only after this contract is accepted.

## Goal

Publish a versioned `study-agent-harness` Python package with one curated,
provider-neutral `study_agent.api` facade. The foundation makes existing
event, source, capability, artifact, assessment, and recall behavior safe for
downstream use without introducing the future job kernel or product policy.
The first adoption artifact is a clean package boundary that Cardine can pin,
install, and consume through an anti-corruption adapter.

## Scope

In scope:

- a machine-readable public import manifest and root version/facade surface;
- a closed public failure taxonomy and host-supplied authority context;
- versioned event envelopes, deterministic upcasters, and immutable module
  registration;
- narrow storage, clock, ID, repository, blob, and replay ports plus a
  reusable offline contract kit;
- immutable source/revision/blob identity and citation resolution;
- explicit, namespaced, manifested, permissioned capability registration;
- generic artifact proposal/revision/decision lifecycle, assessment ledger
  contracts, and recall/scheduling ports;
- dependency-injected async runtime services with a sync convenience facade;
- package namespace, entry-point, optional-extra, and wheel/sdist boundaries;
- release evidence and semver gates for the first Cardine adoption pin.

Out of scope:

- durable Job/lease/retry/queue orchestration or a generic workflow engine;
- workers for hierarchical flashcards, web evidence, or sealed verification;
- Decision Trace or remote telemetry; these belong to the future runtime spec;
- Cardine curriculum, authority/currency/integrity policy, learner model,
  readiness, planning, UI, auth, deployment, or product commands;
- a hosted service, organizations, billing, sharing, or cross-user approvals;
- a Pi/runtime dependency, vendored agent framework, provider-specific core,
  arbitrary network fetch, or mandatory third-party dependency;
- a permanent compatibility bridge for copied Cardine `study_agent` modules.

## Ownership and invariants

- Harness owns portable mechanisms, schemas, transitions, validation, replay,
  and trust boundaries. Cardine owns academic meaning and product policy.
- The append-only per-course event stream is canonical. Projections,
  snapshots, indexes, caches, runs, and diagnostics are rebuildable or
  operational and never independent authorities.
- Models and providers supply transport or proposals only. They cannot mint
  identity, grants, scopes, policy, parentage, approvals, or canonical
  outcomes.
- Only a Host creates principals, grants, and scopes. `HUMAN` represents an
  authenticated owner, `SERVICE` represents authorized injected policy, and
  `MODEL` is untrusted and cannot approve or commit durable effects.
- Unknown, malformed, stale, unauthorized, conflicting, or ungrounded input
  fails closed. Adapter exceptions are translated at the facade.
- Durable commands carry idempotency keys. Equal key plus equal canonical
  input converges on the prior result; equal key plus different input is a
  conflict. Cancellation is cooperative before commit and never rolls back a
  committed event.
- Sources are immutable and content-addressed. A source revision, normalized
  substrate, citation, and derived projection have separate identities.
- Generated artifacts remain proposals until an explicit authorized decision.
  Generic lifecycle contracts never infer Cardine artifact kinds or policy.
- Public service surfaces are async-first where execution may suspend. A sync
  facade calls the same async implementation and is not a second runtime.
- Harness never imports Cardine. The public facade exposes opaque host IDs for
  curriculum, objective, profile, and other product-owned references.

## Public package contract

The package distribution is `study-agent-harness`; the sole regular runtime
namespace is `study_agent`. The curated public boundary is:

```text
study_agent
  ├── __version__
  └── api
      ├── runtime
      ├── authority
      ├── storage
      ├── sources
      ├── capabilities
      ├── artifacts
      ├── assessments
      └── recall
```

`study_agent.api` publishes an immutable `PublicManifest` with facade version,
package version, subfacade names, exported symbols, schema versions, and
supported Python versions. Importing the root package must not import model,
provider, UI, CLI, filesystem, FSRS, or optional-extra modules. Internal
modules remain implementation details without a semver guarantee.

Composition is explicit. A host supplies a principal, repository, storage
ports, clock, ID factory, model adapter, and policy through one immutable
dependency bundle. No global locator, singleton, import-time registration, or
environment-driven auto-configuration is part of the foundation.

The base install has no mandatory dependencies beyond Python 3.12/3.13
standard library. SQLite is a built-in adapter. OpenAI, FSRS, PDF, telemetry,
and other integrations are optional extras or host-owned adapters.

## Slice graph

| Slice | Seam | Depends on | Independently observable result |
| --- | --- | --- | --- |
| PF-01 | `study_agent.api` manifest and root facade | — | Import manifest test passes without implementation imports |
| PF-02 | failure taxonomy and `AuthorityContext` | PF-01 | Safe typed failures and actor/grant checks |
| PF-03 | event envelope, upcasters, `KernelModule` | PF-01, PF-02 | Versioned append/replay and immutable module registration |
| PF-04 | storage/blob/replay ports and contract kit | PF-01..PF-03 | SQLite/filesystem/memory adapters pass shared contracts |
| PF-05 | source/revision/citation ports | PF-03, PF-04 | Content-addressed source and citation round trips |
| PF-06 | capability manifests and registry | PF-01..PF-04 | Explicit trusted registration and fail-closed dispatch |
| PF-07 | artifact, assessment, and recall facades | PF-03..PF-06 | Proposal/ledger/due-view replay contracts remain portable |
| PF-08 | async runtime and sync wrapper | PF-01..PF-07 | Same runtime serves async and sync host calls |
| PF-09 | package/namespace/entry-point boundary | PF-01, PF-06, PF-08 | Harness co-installs with a positive synthetic downstream fixture; the copied pre-adoption Cardine artifact is rejected by the negative fixture; actual Cardine co-install remains CA-04/CA-10-only |
| PF-10 | adoption release evidence and semver gates | PF-01..PF-09 | Clean artifacts, offline gates, and an exact `0.3.0` adoption pin |
| PF-11 | stable facade promotion | PF-10 + signed/hashed CA-08 installed-parity evidence | An executable evidence-only gate promotes the curated facade to `1.0.0`; it has no Cardine import or test dependency |

PF-01 through PF-04 establish the kernel boundary. PF-05 through PF-07
stabilize existing domain families. PF-08 composes them without adding
autonomous planning. PF-09 and PF-10 are distribution/release gates, not new
domain behavior. PF-11 is a post-adoption compatibility-evidence gate and
does not add runtime behavior.

## Review map

Human review is required at these non-blocking checkpoints during implementation:

- PF-01: inspect the import manifest for accidental private exports or eager
  optional imports.
- PF-02/PF-03: inspect authority and event ownership for model write paths,
  unsafe adapter errors, and duplicate canonical facts.
- PF-04/PF-05: inspect replay, blob immutability, citation binding, and path
  ownership; verify no derived text can act as primary evidence.
- PF-06/PF-07: inspect plugin registration, proposal approval boundaries,
  opaque Cardine references, and recall policy ownership.
- PF-08: inspect dependency injection and prove sync calls delegate to the
  async implementation.
- PF-09/PF-10: inspect wheel/sdist contents, entry points, dependency metadata,
  Python matrix, and the positive/negative side-by-side installation cycle.
- PF-11: inspect the signed/hashed CA-08 installed-parity evidence, exact
  `1.0.0` promotion record, and the absence of Cardine imports/tests in the
  Harness gate.

Each checkpoint is non-blocking for implementation progress. The implementing
agent records the evidence and rationale in the slice log; silence is not a
reason to hold an otherwise verified slice.

## Cross-slice verification

The narrow checks in each slice are mandatory. The final foundation gate is:

```text
git diff --check
uv run --python 3.12 --extra dev ruff check src tests
uv run --python 3.13 --extra dev ruff check src tests
uv run --python 3.12 --extra dev mypy
uv run --python 3.13 --extra dev mypy
uv run --python 3.12 --extra dev pytest -q
uv run --python 3.13 --extra dev pytest -q
uv build --out-dir /tmp/study-agent-harness-package-foundation
```

The package must also pass a clean-wheel/sdist install smoke on Python 3.12
and 3.13, a base dependency-free install smoke, a public import-manifest
test, the reusable event/blob/replay/capability contract kit, and the PF-09
positive/negative co-install cycle. The positive fixture owns only `cardine`;
the copied pre-adoption Cardine artifact is a deliberate red fixture until
CA-04/CA-10 removes its `study_agent` package and legacy commands. Foundation
detects that collision rather than claiming to repair it. Actual Cardine
co-install/parity is CA-04/CA-10-only. CI installs the built artifact and
never a sibling checkout or `PYTHONPATH` injection.

PF-11 runs only after CA-08 has produced an installed-parity report. The
promotion command accepts a detached signature and SHA-256 commitments for
the report and the tested artifacts, verifies them against the declared trust
input, and writes a `1.0.0` facade-promotion record. It consumes no Cardine
module, source tree, or Cardine test; orchestration records the evidence
outside the Harness package.

## Resolved implementation notes

The following details are intentionally left to the owning slice because they
do not alter the approved public contract: exact private module factoring,
fixture directory names under `tests/contract`, whether a synchronous adapter
uses a worker thread internally, and the text of release notes. A slice may
settle these details locally while preserving its exact types, failure
semantics, ownership, and verification commands. Any new cross-package
boundary, dependency, schema, or public export requires returning to the
specification before implementation continues.
