# Task Bead: GAP-00 boundary, threat model, and glossary approval

Status: Done — approved 2026-07-16
Priority: P0
Type: contract
Depends On: none

## Outcome

ADR-0011 and the feature spec are accepted with an explicit authority, privacy,
retention, and promotion boundary before code is dispatched.

## Slice Strategy

contract

Fresh Context Fit: yes

## Spec Coverage

- Separate operational feedback from canonical study history.
- Preserve exact seven StudyTools and require one maintainer promotion gate.

## Grilling Evidence

- Session/artifact: 2026-07-16 user discussion plus repository research.
- Decision state: approved by maintainer on 2026-07-16.
- ADR/glossary changes: ADR-0011 and the feature-spec Domain Model.

## Worker Profile

reuse `architect` plus `security-reviewer`

Rationale: the bead fixes public authority and hostile-input boundaries; no
production implementation belongs here.

## What To Do

- Confirm reporting is local-only by default and outside course events.
- Confirm the host tool cannot open issues, run workarounds, or start code.
- Confirm one accepted decision may promote a visible proposal into the normal
  Flywheel implementation gates but never merge/release/deploy.
- Freeze closed vocabularies, safe metadata, retention defaults, and consent for
  off-device export.

## Acceptance Criteria

- [x] No unresolved architecture, privacy, authority, or product decision.
- [x] Hostile filename/content/prompt-injection threat model is complete.
- [x] Glossary distinguishes limitation, observation, workaround, report,
  proposal, decision, promotion, and resolution.

## Verification

- Independent architecture and security review: no open P0/P1 finding.

## Out Of Scope

- Production code, GitHub synchronization, or automatic conversion.
