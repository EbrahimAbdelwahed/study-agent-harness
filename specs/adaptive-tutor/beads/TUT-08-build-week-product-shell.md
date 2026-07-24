# Task Bead: TUT-08 Build Week product shell

Status: In progress — terminal and localhost browser reference surfaces implemented; final visual/GPT host gates remain
Priority: P1
Type: product tracer-bullet
Depends On: TUT-06

## Worker Profile

create a product-shell profile only after a visual direction is selected; use
independent design QA and accessibility review

## Outcome

A thin conversation-first consumer demonstrates the adaptive tutor without
duplicating behavior or persistence.

## Acceptance Criteria

- [x] Free-form learner entry can act before context is complete.
- [x] Conversation, material, evidence, and conflict states are coherent; due
  review is exposed when the optional TUT-07 capability is installed.
- [x] UI uses the product shell/public contracts and never SQLite/model providers directly.
- [ ] One-command sample journey works offline; configured GPT-5.6 remains an
  explicit host-owned composition rather than an implicit browser mode. The
  offline route is green; a configured GPT-5.6 host journey is still a release
  gate and is not claimed by this local reference server.
- [ ] README, sample data, eval report, and sub-three-minute video script satisfy submission requirements.

## Verification

- Browser journey, accessibility, visual diff/critique, deterministic demo,
  packaging, and full core gates. The deterministic HTTP journey and static
  accessibility markers are covered in TUT-08 tests; fresh production-route
  screenshots/critique and the provisioned full environment gates remain
  release evidence to collect.
