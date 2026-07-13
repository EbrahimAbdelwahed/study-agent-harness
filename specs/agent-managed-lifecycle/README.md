# Agent-managed harness lifecycle

Status: Approved — implementation in progress
Last updated: 2026-07-13

## Next Agent Prompt

Read this README, `docs/decisions/ADR-0003--agent-operated-management-plane.md`,
and slices 02 and 03. Slice 01 is complete. The next wave is slice 02 (offline
tool composition) and slice 03 (explicit lifecycle/retry), which may proceed in
parallel only with disjoint file ownership; both feed slice 04. Do not implement
slice 05 or later before the complete 0.1.1 lane (slices 01–04) has passed its
release gates. Keep the exact seven v0.1 StudyTool contracts and fingerprints
unchanged. Update this section before ending a pass.

Global TODO:

- [x] [01 — operation discovery](slices/01-agent-operation-discovery.md)
- [ ] [02 — offline tool composition](slices/02-offline-tool-composition.md)
- [ ] [03 — explicit lifecycle and retry](slices/03-explicit-lifecycle-and-retry.md)
- [ ] [04 — operator skill and 0.1.1 release](slices/04-operator-skill-and-release.md)
- [ ] [05 — manifest contract](slices/05-manifest-contract.md)
- [ ] [06 — safe repository target](slices/06-safe-repository-target.md)
- [ ] [07 — safe source snapshots](slices/07-safe-source-snapshots.md)
- [ ] [08 — deterministic plan and status](slices/08-deterministic-plan-and-status.md)
- [ ] [09 — convergent apply and recovery](slices/09-convergent-apply-and-recovery.md)

Active warning: `LocalRepository.study_tools()` currently resolves a model even
when a caller only needs manifests or read tools. Slice 02 must correct this
without changing the seven manifest fingerprints or moving behavior into a
model adapter.

Evidence ledger:

- Slice 01: `agent-operations@1`, static StudyTool discovery, and repository-free
  CLI discovery landed with 425 tests passing, one opt-in network smoke skipped,
  Ruff and mypy green. Independent review found and closed the `model_setting`
  wire-type mismatch before approval.

## Goal

An external agent can discover, initialize, populate, verify, and use a local
study harness without bespoke model adapters, hidden interactive state, or
direct persistence access. The agent operates as a trusted automation client;
model-proposed arguments remain untrusted and never select authority.

## Why two releases

The current v0.1 primitives are sufficient for most of the journey but are not
reliably agent-operable: offline tool discovery requires a model, the CLI lacks
structured discovery and course enumeration, and there is no explicit session
start for a crash-retry-safe first ask. These are patch-level operability defects
and belong in 0.1.1.

A desired-state manifest introduces a larger reconciliation, filesystem, and
concurrency contract. It belongs in 0.2 only after the primitive lane is safe.
This prevents the reconciler from hiding or compensating for broken primitives.

## Authority model

```text
agent operator / embedding host
        │ trusted repository, identity, capability and idempotency choices
        ▼
management plane: describe / lifecycle / validate / plan / apply / status
        │ invokes existing application services
        ▼
canonical domain event stream ──► replayable projections

model-proposed JSON ──► exact seven StudyTools ──► skills/playbooks
                              │
                              └── never supplies trusted context
```

- The event stream is the only canonical study state.
- A lifecycle manifest is desired operational intent, never domain truth.
- Plans, receipts, repository config, indexes, and checkpoints are operational
  state and may not acquire domain authority.
- Skills and playbooks continue to own study behavior.
- Model adapters continue to translate technical transport only.
- The trusted host creates `ExecutionContext`; neither a manifest nor model
  arguments may declare principal, capabilities, correlation, session authority,
  study behavior, or idempotency identity. The manifest may select only a
  technical model-transport adapter/configuration for repository initialization;
  it cannot select skills, playbooks, prompts, capabilities, or authority.

## Public contracts

### 0.1.1: `agent-operations@1`

The patch release adds an additive, machine-readable host lane:

- static `describe` output with versioned command effects and the canonical
  seven StudyTool manifests;
- deterministic `course list`;
- explicit, idempotent `session start` with a host-supplied session ID;
- offline composition of manifests and non-model tools;
- an operator skill/playbook documenting `init → populate → doctor → session →
  ask → export`, including retry after lost output.

Existing commands, JSON envelopes, automatic-session convenience behavior, and
the exact seven StudyTools remain compatible. The agent-safe ask path always
supplies stable `session_id` and `idempotency_key`; automatic random identities
remain a human convenience and are not advertised for crash recovery.

### 0.2: desired-state lifecycle v1

An optional `study-agent.manifest.json` describes an explicit repository target,
technical model configuration or offline `null`, explicit course IDs, and
explicit UTF-8 text/Markdown sources. The normative fixture is
[`fixtures/manifest-v1.json`](fixtures/manifest-v1.json). It supports:

```text
study-agent manifest validate [PATH]
study-agent manifest plan [PATH]
study-agent manifest status [PATH]
study-agent manifest apply [PATH] --expect-plan SHA256
```

The manifest argument defaults only to `./study-agent.manifest.json`. Its
required `repository.path` is a non-dot relative path resolved under the
manifest directory; therefore the manifest itself never makes a new repository
non-empty. There is no parent search, recursive discovery, glob, include, URL,
command, template, environment interpolation, dynamic plugin, or arbitrary
Python import.

## Single owners

- `study_agent.tools.builtin`: sole owner of the seven StudyTool definitions.
- `study_agent.tools.registry`: schema, capability, idempotency, invocation,
  and safe error enforcement.
- `study_agent.cli.registry`: one closed `CommandRegistration` per CLI operation,
  containing its parser callback, handler, and serializable agent metadata. The
  parser, dispatcher, and `describe` consume this same registry. This is a small
  CLI-local registry, not a generic command DSL or core framework.
- `study_agent.lifecycle.contracts`: manifest, plan, receipt, and trusted
  `LifecycleAuthority` value contracts.
- `study_agent.lifecycle.planner`: pure desired-versus-observed comparison.
- `study_agent.lifecycle.service`: reconciliation through existing application
  services; no direct SQLite or projection writes.
- `study_agent.adapters.filesystem.source_input`: the one bounded, symlink-safe
  source reader, extracted from the current CLI implementation and consumed by
  both procedural `source add` and lifecycle reconciliation.
- `study_agent.adapters.filesystem.repository_target`: the one no-follow
  resolver/initializer for repository directory targets, consumed by procedural
  init and declarative lifecycle setup.
- `study_agent.adapters.filesystem.lifecycle`: strict manifest discovery and
  loading; it delegates source reads to the shared source-input owner.
- `study_agent.operator_skill`: packaged, versioned operator skill resource and
  fingerprint; the wheel is its sole owner and can extract it offline.
- CLI modules: parsing, composition, and stable JSON serialization only.

No slice may create a second command declaration, source reader, course, source,
session, prompt, tool-manifest, or event-state abstraction. Transitional
compatibility layers are not planned.

## Lifecycle semantics

- Repository target absent → initialize from the exact manifest model config;
  compatible repository → noop; config mismatch → conflict without mutation.
- Course absent → create; identical immutable profile → noop; different profile
  under the same ID → conflict.
- Source absent → ingest; identical revision → noop; changed bytes or metadata →
  new immutable revision.
- Removed manifest entries → warning and no deletion in v1.
- Missing/stale retrieval index → rebuild discardable operational state.
- Apply is atomic per canonical mutation, not across the entire manifest. After
  interruption or lost output, the recovery protocol is `status → plan → apply
  --expect-plan NEW_SHA`. Reusing the old plan SHA performs no new mutation
  unless its next action is still current and verified unfulfilled; otherwise it
  fails stale and requires the new plan.
- An index failure after source commit reports `applied_degraded`; it never
  rolls back or hides the canonical event.

## Security firewalls

- Strict bounded JSON, duplicate-key rejection, closed fields, explicit IDs.
- Explicit `.txt`/`.md` files only; existing 16 MiB per-file limit plus manifest
  count and total-byte limits.
- Paths relative to the manifest directory, with absolute paths, `.`, and `..`
  rejected; every component is no-follow and regular-file checked before and
  after reading.
- Repository targets use their own no-follow directory resolver/initializer;
  validation and later `mkdir(parents=True)` re-resolution is forbidden.
- Additional source roots require a trusted CLI/host option and can never be
  requested from inside the manifest.
- Credentials remain environment values outside state. Discovery may expose the
  credential variable name and availability boolean, never its value.
- Lifecycle commands perform no model/provider calls. Default tests deny network.

## Slice graph

```text
                    ┌──► 02 offline composition ──┐
01 discovery ───────┤                              ├──► 04 operator skill + 0.1.1
                    └──► 03 explicit lifecycle ───┘
                                                     │
                                                     ▼
05 manifest ──► 06 safe target ──► 07 safe sources ──► 08 plan/status
                                                            │
                                                            ▼
                                                 09 apply/recovery + 0.2
```

Each slice has one public seam and its own executable verification. The 0.2
lane depends on the released 0.1.1 host-operation vocabulary.

## Release roadmap

- **0.1.1 — Agent operability and recovery:** slices 01–04.
- **0.2 — Agent-operated desired-state lifecycle:** slices 05–09.
- **0.3 — Study artifacts and richer retrieval:** versioned notes,
  explanations, summaries, flashcards, PDF and optional retrieval adapters.
- **0.4 — Recall and SRS:** review log, scheduler port, FSRS and Anki export.
- **0.5 — Assessment and learner evidence:** attempts, confidence, gaps and
  evidence-derived mastery.
- **0.6 — Planning and advanced pedagogical procedures:** plans, conditions,
  loops, composition and remediation.
- **1.0 — Stable OSS contracts:** migration policy, import/export compatibility,
  calibrated evals, two model transports and two real agent/runtime consumers.

MCP or HTTP may adapt the host seam only when a real consumer justifies it.
They are not prerequisites for agent operability.

## Non-goals

- No generic autonomous-agent loop or agent SDK.
- No eighth StudyTool for repository, course, source, or session setup.
- No setup authority inside model-proposed arguments.
- No Sbobby, hosted product, auth, tenancy, billing, UI, or analytics.
- No provider/model-specific behavior, prompt branch, or adapter per model.
- No remote sources, PDF/audio/vector ingestion, deletion, import, sync,
  multi-writer merge, or cross-course transaction in these releases.
- No dynamic/untrusted skills or executable manifest content.

## Decision log

- Assumed the external agent is a trusted automation host or subprocess caller;
  the model remains an untrusted proposer of schema-bounded arguments.
- Selected two releases rather than one management-plane rewrite.
- Selected an optional desired-state manifest over adding procedural setup tools
  to the model-facing registry.
- Rejected a global all-or-nothing manifest transaction in favor of explicit,
  resumable convergence.
- Rejected automatic config mutation for existing repositories in manifest v1.
- Deferred generic CLI tool invocation until a consumer proves that the Python
  embedding seam is insufficient and its authority policy is specified.

## Required review

This feature requires ADR review, worker decomposition, architecture audit,
security review of the filesystem boundary, behavior tests, and full Python
3.12/3.13 release gates. It does not require prompt evals, RAG quality changes,
UI states, or canonical data migration.
