# Task Bead: GAP-04B first source-format workaround adapter

Status: Scope approved — deferred; blocked on GAP-03, GAP-04A and adapter selection
Priority: P2
Type: tracer-bullet
Depends On: GAP-03, GAP-04A

## Outcome

One explicitly selected local converter demonstrates a sandboxed, provenance-
preserving temporary path without pretending it is native format support.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Optional concrete workaround after the reporting MVP proves useful.

## Grilling Evidence

- Session/artifact: future adapter-specific dependency/security decision.
- Decision state: feature scope approved 2026-07-18; concrete adapter/dependency
  selection intentionally remains a bead-level decision.
- ADR/glossary changes: required if new dependency/effect is approved.

## Worker Profile

create adapter-specific profile only after selection

Rationale: PDF/OCR/audio have materially different dependencies and safety.

## Acceptance Criteria

- [ ] Dependency, sandbox, file limits, race/symlink behavior, quality warning,
  and provenance are explicitly approved and tested.
- [ ] Failure returns a truthful workaround receipt and preserves the gap report.

## Verification

- Adapter-specific hostile-file, quality, provenance, and offline tests.

## Out Of Scope

- Selecting the converter in advance or claiming general format support.
