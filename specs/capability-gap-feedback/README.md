# Feature Spec: Capability-gap feedback and controlled improvement promotion

Status: Approved — implementation graph accepted 2026-07-18
Owner: orchestrator + maintainer
Date: 2026-07-16

## Grilling Evidence

- Session/artifact: 2026-07-16 user discussion, repository research, and
  ADR-0011 boundary audit.
- Decision state: ADR-0011 and the complete GAP graph approved; dispatch remains
  dependency-gated and adapter-specific selections stay explicit.
- ADR/glossary changes: ADR-0011; Capability Gap Plane, gap report, workaround
  receipt, outbox bundle, improvement proposal.

## Goal

Allow the main tutor to report a real unsupported learner need once, continue
with an authorized temporary workaround where possible, and feed a private,
sanitized, deduplicated signal into the existing Flywheel for one consolidated
maintainer decision before implementation.

## Problem

The harness currently fails safely on unsupported operations but cannot learn
which missing formats, integrations, or study behaviors matter in real use.
Manual reporting loses context and does not connect naturally to the existing
decision/spec/bead workflow. A direct agent-to-issue or agent-to-code loop would
be unsafe and would confuse model observation with engineering authority.

## Users

- Learner using a tutor host who needs a currently unsupported behavior.
- Maintainer deciding which repeated gaps should enter the OSS roadmap.
- Engineering agents consuming an accepted, evidence-backed improvement package.

## In Scope

- Optional local capability-gap reporting surface for tutor hosts.
- Closed categories: `input_format`, `output_format`, `study_behavior`,
  `integration`, `accessibility`, `performance`, and `reliability`.
- Structured observation and host-trusted workaround receipts; no free text in
  the portable/deduplicated MVP record.
- Stable identity, deterministic structured deduplication, occurrence aggregation, bounded
  retention, local query, and explicit redacted export.
- A transport-neutral outbox port, local default, and optional authenticated
  private intake delivery for hosted production.
- Flywheel import, reproduction attempt, active-work deduplication, technical
  option generation, and one structured maintainer decision per immutable
  proposal.
- Accepted promotion into the normal approved spec/bead/implementation workflow.
- Offline scripted end-to-end scenario for an unsupported study-material format.

## Out of Scope

- Automatic file conversion, package/plugin installation, web search, arbitrary
  command execution, or authority escalation.
- Raw learner messages, material bodies, filenames, absolute paths, secrets,
  provider-private data, or private model reasoning in reports.
- Model-authored priority, severity, roadmap ownership, implementation choice,
  issue body, or acceptance decision.
- Automatic GitHub issues, pull requests, merges, releases, deployments, or
  telemetry upload.
- Direct public access to Flywheel or a core dependency on HTTP, queues, cloud
  services, devkit, or a particular deployment provider.
- Canonical course events, learner evidence, mastery, tutor memory, or changes to
  the seven StudyTools.

## User Stories

- As a learner, I receive an honest limitation and a safe available workaround
  without the tutor pretending the unsupported material was processed.
- As a tutor host, I can record one bounded gap report idempotently without
  leaking the conversation or granting development authority.
- As a maintainer, I receive grouped evidence, reproduction status, technical
  options, recommendation, and proposed scope in one decision request.
- As an engineering agent, I can start only from an accepted, versioned proposal
  with normal Flywheel quality gates.

## Domain Model

- `CapabilityGapObservation`: closed requested-operation, target-family, impact,
  and limitation identifiers tied to contract fingerprints and a trusted receipt.
- `WorkaroundReceipt`: `none_available|suggested|attempted_succeeded|
  attempted_failed`, authorized capability/tool identities used, and a bounded
  non-executable summary.
- `GapKeyV1`: domain-separated SHA-256 over canonical JSON with schema version,
  category, requested-operation kind, safe target kind, trusted limitation code,
  relevant contract identity, and contract major; never learner/model text.
- `CapabilityGapRecord`: local operational aggregate with first/last seen,
  occurrence count, reproducibility, export state, and resolution.
- `GapOutboxBundle`: strict redacted portable records plus schema and harness
  fingerprints.
- `GapOutboxTransport`: host-injected delivery boundary; local by default, with
  optional authenticated delivery to a private durable inbox.
- `DeliveryImportId`: inbox-derived hash of authenticated sender scope plus
  bundle fingerprint, used only to make one delivery contribute at most once;
  it is not proposal evidence and aggregation still uses `GapKeyV1`.
- `ImprovementProposal`: Flywheel-owned reproduction evidence, duplicate links,
  options, recommendation, draft ADR/spec/beads, and verification plan.
- `GapResolution`: `duplicate|rejected|deferred|accepted`; only the maintainer or
  trusted workflow authority can set it.

## API / Interface Contract

```text
report_capability_gap@1(
  category,
  requested_operation_kind,
  requested_target_family,
  impact_kind,
  workaround_suggestion_kind?
) + trusted_host_context(
  limitation_receipt?,
  verified_workaround_execution_receipt?
) -> {
  report_id,
  gap_key,
  occurrence_count,
  disposition: recorded | deduplicated | rate_limited,
  local_only: true
}
```

Trusted host context supplies authority, harness version, correlation,
idempotency identity, and optional course/session linkage. Model arguments cannot
set those values or claim that a workaround ran. The result does not promise that
the feature will be built.

## Prompt Behavior

- Prompt IDs affected: reference tutor-host policy only; core reporting requires
  no model call or generation prompt.
- The tutor reports only after a typed unsupported result or an explicit
  capability comparison proves the limitation.
- It states the limitation to the learner, tries only an already-authorized
  workaround, and never claims success without a successful receipt.
- Eval fixtures cover prompt injection, repeated requests, fake priority,
  unsupported extension, secret/path text, and no-workaround behavior.

## RAG / Source Grounding

- No RAG is required for recording a gap.
- The report references typed runtime evidence and safe metadata, not source
  contents.
- Flywheel reproduction records exact local fixtures or an explicit
  `not_reproducible_from_export` limitation.

## UX Notes

- Reporting must not block the learner after the limitation/workaround is shown.
- Local-only state and optional export are explicit.
- Repeated equivalent gaps produce one aggregate, not repeated notifications.
- Maintainer UI/CLI shows evidence, privacy redactions, duplicates, proposal,
  choices, and the exact action acceptance will authorize.
- Transport failure never interrupts study; the local report remains pending and
  the host may retry later.

## Risks

- Spam or roadmap manipulation from prompt injection.
- Sensitive path/content leakage through free text.
- Deduplication collapsing materially different requests.
- A workaround suggestion being mistaken for successful ingestion.
- “Accepted” silently expanding into publish/merge authority.

## Acceptance Criteria

- [ ] Exact retry records one occurrence; separate equivalent observations
  aggregate under one stable gap key.
- [ ] Reports containing secrets, paths, filenames, source bodies, arbitrary
  commands, unknown fields, or free-form text fail before persistence; these
  fields are absent from the portable schema.
- [ ] Recording and querying gaps do not append course events or change the seven
  StudyTools/capability manifests.
- [ ] A workaround receipt can name only capabilities/tools already present in
  the trusted host grant; attempted outcomes require a host-trusted execution
  receipt and reporting never executes the workaround.
- [ ] Default storage and export are local and credential-free; hosted delivery
  is explicit, authenticated, optional, and implemented outside core.
- [ ] A hosted transport delivers exact redacted bundle bytes at least once to a
  private inbox, deduplicates by authenticated sender scope plus bundle
  fingerprint, acknowledges only durable persistence, and exposes no Flywheel
  operation to the tutor. The derived delivery ID is importer idempotency context
  only; sender scope and delivery ID never enter proposal evidence.
- [ ] Flywheel import is deterministic, deduplicates against reports and active
  beads/specs, and creates one immutable proposal plus one unresolved decision
  request per gap key/equivalent cohort; independent gaps never share approval.
- [ ] Before acceptance, no approved spec, bead state, goal, code, dependency,
  GitHub issue, or publication changes.
- [ ] Acceptance promotes the reviewed proposal through normal grill, worker,
  test, semantic-review, and publication gates; rejection/defer/duplicate do not.
- [ ] An offline unsupported-format story reaches the learner workaround and
  maintainer decision without leaking learner material or contaminating tutor
  context.

## Verification

- Unit: codecs, fingerprints, redaction rejection, deduplication, rate policy,
  lifecycle, and resolution authority.
- Integration: process restart, outbox roundtrip, Flywheel import, decision
  resolution, promotion idempotency, transport retry, duplicate delivery, inbox
  quarantine, and recovery.
- Evals: unsupported format, injection, duplicate, fake severity, workaround
  success/failure, and non-reproducible report.
- Manual: inspect one local report, proposal, and accepted/rejected path.

## Open Questions

- Optional GitHub issue synchronization is deferred until the local loop proves
  useful; it requires its own outbound-adapter decision.
- Retention and aggregation thresholds should be host policy with conservative
  defaults, not core roadmap priority.

## Decision Log

- Use a separate optional plane rather than canonical learner state.
- Preserve the seven StudyTools; expose a host tool backed by an injected sink.
- Keep reports local by default and require explicit export.
- In hosted production, deliver only the redacted bundle to a private durable
  inbox; a factory worker, not the tutor, invokes Flywheel.
- Prepare each scoped technical proposal before asking for its one maintainer
  decision; consolidate only exact or explicitly reviewed equivalents.
- Acceptance may start implementation gates but never merge, release, or deploy.

## Task Beads

- `GAP-00`: approve boundary, threat model, and glossary.
- `GAP-01`: provider-neutral report contracts and operational registry.
- `GAP-02`: agent-facing host report tool and service.
- `GAP-03`: unsupported source-format tracer bullet.
- `GAP-04A`: allowlisted workaround registry and receipts.
- `GAP-04B`: first explicitly approved source-format workaround adapter.
- `GAP-05`: outbox-to-proposal parent.
  - `GAP-05A`: strict redacted harness outbox.
  - `GAP-05B`: devkit import, deduplication, and reproduction.
  - `GAP-05C`: immutable proposal and one decision request per cohort.
  - `GAP-05D`: hosted private intake transport and durable inbox.
- `GAP-06`: maintainer decision and accepted promotion lane.
- `GAP-07`: adversarial end-to-end closure.
- `GAP-07B`: optional hosted transport-to-import closure.
- `GAP-08`: optional accepted-only GitHub synchronization and resolution
  feedback, deferred beyond the MVP.

## Execution Order

```text
GAP-00 done
  ├─ GAP-01 registry → GAP-02 host tool
  │                    ├─ GAP-03 source-format tracer (also needs TUT-06)
  │                    └─ GAP-05A outbox
  │                         ├─ GAP-05B devkit import → GAP-05C proposal → GAP-06 promotion
  │                         └─ GAP-05D hosted transport
  │
  └─ GAP-04A workaround registry
       └─ GAP-04B concrete source workaround (also needs GAP-03 + adapter choice)

GAP-03 + GAP-06 → GAP-07 local end-to-end closure
GAP-05B + GAP-05D → GAP-07B hosted transport closure
GAP-07 → GAP-08 optional GitHub adapter
```

Completed: `GAP-00`, `GAP-01`, `GAP-02`, `GAP-03`, `GAP-04A`, and `GAP-05A`.
The next dependency-ready bead is `GAP-05B`, which belongs in the private
devkit repository. `GAP-04B`, `GAP-05D`, `GAP-07B`, and `GAP-08` also require
the named concrete adapter decision before dispatch.
