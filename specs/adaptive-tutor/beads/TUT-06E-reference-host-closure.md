# Task Bead: TUT-06E reference tutor-host closure

Status: Implementation complete — clean-wheel build gate pending
Priority: P0
Type: closure
Depends On: TUT-06B, TUT-06C, TUT-06D

## Outcome

The scripted and optional OpenAI hosts prove the same bounded adaptive-tutor
contract end to end, with adversarial recovery coverage and honest setup,
privacy, API-key, subscription, and file-handling documentation.

## Acceptance Criteria

- [x] One deterministic offline demo covers free-form learner entry, progressive
  context, capability discovery/selection, direct completion, clarification
  suspension/resume, learner-evidence refresh, and a captured-file proposal.
- [x] The same host-runner trace and gateway-call contract is exercised with the
  scripted decision adapter and recorded OpenAI Responses adapter fixtures.
- [x] Adversarial evals cover authority/idempotency/grant injection, hidden
  assessment answers, prompt/tool injection in learner/source content, forged
  continuation/file descriptors, cross-owner references, stale state, exact
  retry, provider failures, step exhaustion, and interruption at every boundary.
- [x] Failed, interrupted, stale, terminated, cancelled, malformed, or
  budget-exhausted host work cannot be presented as a completed capability or
  append an unauthorized canonical event.
- [ ] Clean install without optional extras runs the full scripted demo and
  imports all public core contracts. Clean install with the OpenAI extra runs
  adapter conformance without requiring network access.
- [x] Opt-in live smoke is environment-gated, names the explicit model id used,
  transmits only its documented fixture, and is never part of default CI.
- [x] Documentation explains trusted host responsibilities, limits, retry and
  stale semantics, source-data privacy, API-key environment setup, optional SDK
  install, configurable model id, cost/network expectations, and explicit lack
  of ChatGPT subscription support.
- [x] Architecture gates prove provider/SDK imports remain optional and outside
  core owners, scripted/live parity, no second gateway or canonical state owner,
  and no change to the seven StudyTools.

## Verification

- Full offline unit/contract/integration/eval/architecture suite; clean-wheel
  matrix with and without the optional extra; docs example; opt-in live smoke;
  Ruff; strict mypy; `git diff --check`.
