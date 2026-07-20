# Task Bead: TUT-04C0 shared flashcard batch and trusted dispatch

Status: Done
Priority: P0
Type: tracer-bullet
Depends On: TUT-04A, TUT-03

## Outcome

One public `propose_flashcards@1` manifest accepts a bounded task envelope while
a composition-root dispatcher selects a profile-specific binding from a trusted
selection receipt that model content cannot alter.

## Acceptance Criteria

- [x] Shared candidate batch schema is bounded to 24, uses temporary candidate
  linkage only, and contains no canonical IDs, decisions, Anki fields, provider
  selectors, credentials, raw HTML, or state writes.
- [x] Dispatcher defaults only to hybrid and requires a trusted evidence basis
  for morphology; selected profile/prompt/playbook/validator pins are closed in
  the binding and continuation.
- [x] Profile selection is absent from model-authored output and cannot be
  changed on retry/resume.

## Verification

- Dispatch/manifest/binding contracts, invalid receipt/retry tests,
  portability/Anki negative fixtures, seven-tool parity, and static gates.
