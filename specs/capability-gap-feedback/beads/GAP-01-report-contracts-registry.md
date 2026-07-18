# Task Bead: GAP-01 capability-gap contracts and operational registry

Status: Approved — dependency-ready
Priority: P0
Type: tracer-bullet
Depends On: GAP-00

## Outcome

A trusted host can idempotently append and query one sanitized gap observation
in a provider-neutral operational registry without touching course state.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Strict report, failure evidence, workaround receipt, gap key, aggregate, and
  resolution contracts.
- Deterministic deduplication, retry, privacy, and state-plane separation.

## Grilling Evidence

- Session/artifact: GAP-00 accepted ADR/threat model.
- Decision state: approved by maintainer on 2026-07-18; no unresolved bead-level
  decision or glossary change.
- ADR/glossary changes: ADR-0011.

## Worker Profile

reuse `implementer`; independent `test-engineer`

Rationale: bounded contracts/store work with security-relevant validation.

## Context

Reuse execution-context authority/idempotency patterns and operational store
ports. Do not reuse the course event stream or the StudyTool registry.

## What To Do

- Add exact immutable contracts and canonical codecs/fingerprints.
- Freeze `GapKeyV1` as domain-separated SHA-256 over sorted-key canonical JSON
  with schema version, category, requested-operation kind, safe target kind,
  trusted limitation code, relevant contract identity, and contract major.
  Existing-key/different-dimensions fails as `gap_key_collision`.
- Bind runtime-error reports to trusted failure receipts; allow explicit learner
  requests without a receipt only as `unverified_request`.
- Derive gap/report identities in core and aggregate observations with exact
  retry semantics and bounded retention.
- Define an inward `CapabilityGapStore` port and reference local SQLite adapter.

## Acceptance Criteria

- [ ] Exact retry is one observation; equivalent new observations increment one
  aggregate without retaining repeated raw text.
- [ ] Model input cannot set trusted error, runtime version, authority, IDs,
  priority, severity, status, or resolution.
- [ ] The persistent/portable contract has no free-text field. Paths, filenames,
  secrets, material text, commands, executable payloads, unknown fields, and
  oversized values are structurally rejected before persistence.
- [ ] Keys are byte-deterministic across processes and never include model text;
  distinct requested-operation kinds such as PDF text extraction versus table
  preservation cannot collapse solely because the format family matches.
- [ ] Replay/process restart is deterministic and no course event is appended.
- [ ] Exact-seven StudyTool and capability-manifest golden tests remain unchanged.

## Verification

- Focused unit/integration tests, secret/path fuzz fixtures, process restart,
  Ruff, strict mypy, architecture/tool parity, and full offline suite.

## Out Of Scope

- Agent tool exposure, workaround execution, outbox, Flywheel, UI, and GitHub.
