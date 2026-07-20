# Task Bead: GAP-08 optional GitHub synchronization and resolution feedback

Status: Scope approved — deferred; blocked on GAP-07 and outbound-adapter selection
Priority: P3
Type: expand
Depends On: GAP-07

## Outcome

Accepted proposals may optionally synchronize a redacted issue and later map a
released capability version back to the local gap without making GitHub canonical.

## Slice Strategy

expand

Fresh Context Fit: yes

## Spec Coverage

- Deferred external collaboration and closed-loop resolution signal.

## Grilling Evidence

- Session/artifact: future GitHub privacy/auth/rate-limit decision.
- Decision state: feature scope approved 2026-07-18; GitHub auth/privacy adapter
  selection remains deferred.
- ADR/glossary changes: outbound adapter ADR required.

## Worker Profile

create `github-gap-sink` only after approval; require `security-reviewer`

## Acceptance Criteria

- [ ] Only accepted proposals can synchronize; credentials stay in the adapter.
- [ ] Redaction, idempotent marker, rate limit, retry, permission failure, and
  issue tamper are safe.
- [ ] GitHub state cannot approve, prioritize, or mutate local Flywheel state.
- [ ] Resolution requires verified release/capability evidence, not issue closure
  text alone.

## Verification

- Opt-in adapter tests with scripted GitHub boundary and zero-network defaults.

## Out Of Scope

- MVP, automatic public issue creation, or GitHub as source of truth.
