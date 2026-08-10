# Feature Spec: Harness Package Foundation

Status: Approved
Owner: orchestrator
Date: 2026-08-09
Run ID: `20260809-harness-package-foundation`

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- Decision state: approved; accelerated grilling rounds 1–75 and final shared-understanding confirmation complete.
- ADR/glossary changes: all ownership and vocabulary decisions are recorded in the handoff; no open ADR or glossary decision remains.

## Goal

Publish `study-agent-harness==0.3.0` with a curated, dependency-injected,
provider-neutral `study_agent.api` facade and portable contract kit, then
promote the unchanged accepted facade to `1.0.0` after downstream installed
parity evidence.

The canonical detailed spec is `specs/package-foundation/README.md`; PF-01
through PF-11 under `specs/package-foundation/slices/` are binding.

## Problem

Harness and pre-adoption Cardine currently ship the same regular Python package,
and Harness internals lack an explicit SemVer boundary. Downstream adoption is
unsafe until namespace, authority, failure, event, module, storage, source,
capability, lifecycle, runtime, and distribution contracts are stable.

## Source Inputs

- Intake: `docs/flywheel-runs/20260809-harness-package-foundation/intake.md`
- Context pack: `docs/flywheel-runs/20260809-harness-package-foundation/context-pack.md`
- Canonical spec: `specs/package-foundation/README.md`
- Context authority: `CONTEXT.md`, `CONTEXT-MAP.md`

## Users

- Library hosts that need portable study runtime contracts.
- Cardine as a downstream product consumer through its own anti-corruption layer.

## In Scope

- PF-01 through PF-11 exactly as materialized in the canonical spec.
- Public facade, explicit DI, typed failures/authority, event upcasting,
  KernelModule, ports/contract kit, existing portable lifecycle facades,
  async-first runtime, artifact builds, 0.3 release, and evidence-only 1.0 promotion.

## Out of Scope

- Jobs, Decision Trace, web evidence, sealed verification, Cardine policy/UI,
  provider selection, mandatory third-party dependencies, source mirroring, or
  Harness-side workarounds for the copied Cardine namespace.

## User Stories

- As a host, I can import only `study_agent.api`, inject dependencies, and run
  portable behavior without importing internal modules.
- As a release consumer, I can verify an explicit manifest, contract kit,
  artifact provenance, and SemVer promise.

## Domain Model

Affected portable owners are `PublicManifest`, `HarnessFailure`, authority
values, `EventEnvelope`, upcasters, `KernelModule`, storage/source/citation
ports, capability manifests, portable artifact/assessment/recall contracts,
and `HarnessRuntime`. The canonical spec defines exact fields and invariants.

## API / Interface Contract

The only stable tree is `study_agent.api.{runtime,authority,storage,sources,
capabilities,artifacts,assessments,recall,errors,events,kernel}` plus version.
Exact inputs, outputs, failures, idempotency, cancellation, and registration
rules are binding from PF-01–PF-08.

## Prompt Behavior

- Prompt IDs affected: none.
- Course profile inputs: opaque host references only.
- Output schema: typed facade values; raw provider output never crosses it.
- Grounding requirements: source/citation integrity remains fail-closed.
- Eval fixtures required: offline contract/replay fixtures only.

## RAG / Source Grounding

- Required sources: immutable SourceRevision/blob/lineage/citation owners.
- Citation behavior: exact revision-bound resolution.
- Unsupported-answer behavior: typed validation/integrity failure; no fabricated support.

## UX Notes

- Loading state: not applicable to the library package.
- Empty state: typed empty portable views.
- Error state: closed safe failure taxonomy.
- Accessibility: no product UI is introduced.

## Risks

- Accidental private exports, duplicate canonical event representations,
  optional-dependency eager imports, namespace collision, or a reverse Cardine dependency.

## Acceptance Criteria

- [ ] Every PF slice passes its focused verification and full offline gate.
- [ ] Built artifacts install on Python 3.12/3.13 with standard-library-only base.
- [ ] Synthetic downstream co-install passes and copied Cardine collision is detected.
- [ ] Cardine installed-parity evidence supports the 1.0 promotion without a Harness import/test dependency.

## Verification

- Unit: slice-specific unit/contract commands.
- Integration: replay, external-host, artifact-install, positive/negative collision fixtures.
- Evals: deterministic contract/replay equality.
- Manual: inspect public manifest, wheel/sdist contents, checksums, and promotion evidence.

## Open Questions

- None. Public contracts, release order, and removal conditions are approved.

## Task Beads

- `PF-01`: Public manifest and ownership firewall
- `PF-02`: Failures and authority
- `PF-03`: Events, upcasting, and module registration
- `PF-04`: Storage contract kit
- `PF-05`: Sources and citations
- `PF-06`: Capabilities
- `PF-07`: Artifacts, assessments, and recall
- `PF-08`: Async-first runtime
- `PF-09`: Distribution isolation
- `PF-10`: Publish adoption release 0.3.0
- `PF-11`: Stable facade promotion 1.0.0
