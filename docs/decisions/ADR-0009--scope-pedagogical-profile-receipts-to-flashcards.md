# ADR-0009: Scope pedagogical-profile receipts to flashcards

Date: 2026-07-15
Status: Accepted

## Context

ADR-0008 defines two pedagogical profiles for flashcard generation, but its
provenance paragraph can be read as requiring one of those profiles for every
generated artifact. That would make an exam blueprint or study brief falsely
claim use of a flashcard method.

## Decision

`GeneratedArtifactProvenance.profile_selection` is optional as a standalone
provenance leaf. The canonical artifact-revision boundary makes the kind-aware
rule strict:

- a flashcard requires a closed-catalog profile receipt matching its content;
- every non-flashcard artifact forbids a profile receipt;
- an unknown profile id or version is rejected before canonical identity is
  assigned.

Prompt, model, validator, run, read-dependency, and source proof remain required
for every generated artifact as specified by ADR-0008.

## Consequences

- Exam-blueprint, assessment-item, and study-brief provenance stays truthful.
- Profile policy cannot leak into artifact kinds it does not govern.
- Future profiled artifact kinds require a new explicit contract rather than
  reusing a flashcard profile implicitly.

## Alternatives Considered

- Attach the default hybrid profile to every generated artifact: rejected
  because it would record a method that was neither selected nor used.
- Generalize the two flashcard profiles into a global behavior profile: rejected
  because it weakens the closed, task-specific behavior boundary.
