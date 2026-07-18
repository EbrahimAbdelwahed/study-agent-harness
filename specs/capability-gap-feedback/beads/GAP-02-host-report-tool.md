# Task Bead: GAP-02 agent-facing host report tool

Status: Approved — blocked on GAP-01 implementation
Priority: P0
Type: expand
Depends On: GAP-01

## Outcome

An embedding tutor host can expose `report_capability_gap@1` to its main agent
and receive a compact local-only receipt through an injected `FeatureGapSink`.

## Slice Strategy

expand

Fresh Context Fit: yes

## Spec Coverage

- Agent-facing reporting with trusted context, idempotency, safe result, and no
  external/canonical authority.

## Grilling Evidence

- Session/artifact: GAP-00 plus GAP-01 contracts.
- Decision state: scope approved 2026-07-18; implementation dependency remains.
- ADR/glossary changes: none expected.

## Worker Profile

reuse `implementer`; require `security-reviewer`

Rationale: narrow host surface with untrusted model arguments and operational
write authority.

## What To Do

- Add a separately discoverable host-tool manifest/service; do not register it
  in `StudyToolRegistry` or `StudyCapabilityGateway`.
- Accept only closed model-proposed category/operation/target/impact and optional
  suggestion enums; no free text enters the record.
- Bind authority, runtime/error receipt, grants, correlation, retry identity, and
  any actual workaround execution receipt out of band.
- Derive `attempted_succeeded|attempted_failed` only from the trusted execution
  receipt. The model cannot author an attempted outcome merely by naming an
  already-granted tool/capability; the service records rather than executes it.
- Return only report/gap identity, occurrence count, disposition, and
  `local_only=true`; expose detail only through a trusted admin view.

## Acceptance Criteria

- [ ] The main agent can record/deduplicate a supported report without a model
  call inside the reporting service.
- [ ] Spoofed error/grant/identity, arbitrary issue body, and external target
  fields fail closed.
- [ ] A model-authored attempted-success/failure fails without the matching
  host-trusted execution receipt; a closed suggestion remains non-executed.
- [ ] Reporting does not block the learner flow and grants no new authority.
- [ ] Seven StudyTools and existing capability discovery remain byte-identical.

## Verification

- Contract/golden, authority, retry, hostile argument, compact/detail view,
  architecture, Ruff, strict mypy, and full offline tests.

## Out Of Scope

- Tutor policy, conversion, outbox, dev workflow, or external tickets.
