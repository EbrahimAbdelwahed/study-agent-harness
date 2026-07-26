# KB-22C: Optional model projector

Status: Proposed — prompt/provider decision required
Risk: High
Depends On: KB-08, KB-16
Parent: KB-22

## Outcome

An optional generic model worker can derive bounded handles, summaries, and
concept labels from a unit plus ancestors while structural/lexical projections
remain the permanent fallback.

## Acceptance criteria

- [ ] Prompt and output schema are versioned, closed, provider-neutral, and
  tested with scripted models.
- [ ] Input includes exact unit/ancestor citations and treats source text as
  untrusted data.
- [ ] Output claims are derived, non-citable, lineage-linked, and cannot change
  unit identity or canonical state.
- [ ] Malformed/oversized/injected output, timeout, rate limit, and missing
  provider fall back to free projection without hiding the failure.
- [ ] Artifact identity binds unit/input, prompt, model, adapter, and policy.
- [ ] Projection eval quantifies gain over structural and lexical projectors
  before default use.

## Verification

- Scripted model contract/eval fixtures, injection, recovery, invalidation,
  provenance, optional-install CI, and provider security review.

## Out of scope

- Answer synthesis, tutor behavior, figure cards, or hardcoded provider choice.
