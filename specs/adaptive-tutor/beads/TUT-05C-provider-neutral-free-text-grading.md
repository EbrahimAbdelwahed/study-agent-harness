# Task Bead: TUT-05C provider-neutral free-text grading

Status: Done
Priority: P0
Type: expand
Depends On: TUT-05B, TUT-03

## Outcome

`grade_response@1` evaluates one committed free-text attempt through a bounded,
provider-neutral skill/playbook procedure and returns a validated proposal with
no canonical write authority.

## Acceptance Criteria

- [ ] The capability manifest accepts only an opaque attempt identity and
  presentation language; provider/model selectors, raw authority, repositories,
  responses, rubrics, and caller-authored evidence are forbidden.
- [ ] A trusted `assessment.prepare_grade_scope` bridge resolves the exact
  canonical attempt, presentation, accepted item, rubric, expected response,
  and artifact source commitments into one request-bound prompt projection.
- [ ] The playbook is exactly Tool -> readiness/security validation -> one
  Model -> integrity validation, does not suspend, and has an empty
  `StateWritePolicy`.
- [ ] Learner response, artifact text, and evidence are explicitly untrusted
  data rather than instructions. Prompt injection, hidden prompt requests,
  provider/tool choices, learner advice, mastery, and scheduling fail closed.
- [ ] Validated capability output is a strict `graded | needs_review | ungradable`
  union. Model output contains only the ordered criterion proposals, each with
  `met | not_met | uncertain`, a bounded rationale, evidence handles, and bounded
  confidence; overall status and score are absent and cannot be model-authored.
- [ ] The integrity validator derives the final union and score: all determinate
  criteria produce `graded`, any `uncertain` produces `needs_review`, and the
  exact score is `met_count/criterion_count` without reduction. `ungradable`
  requires an explicit valid evidence-insufficiency result. Unknown evidence,
  missing/duplicate/reordered criteria, stale rubric fingerprints, unsupported
  rationales, extra fields, or malformed output terminate validation.
- [ ] Evidence handles resolve only through the immutable assessment artifact
  provenance and canonical source content.
- [ ] Prompt, skill, playbook, validator, and capability versions are pinned;
  the same behavior runs with scripted or generic model adapters and does not
  expand the seven public StudyTools.
- [ ] The prepared scope binds course/session/attempt/presentation/revision,
  response fingerprint, expected response, ordered rubric fingerprint, accepted
  artifact/source commitments, a redacted prompt projection, and a closed
  evidence-handle map. The caller supplies only attempt identity and language.
- [ ] Learner/artifact text and counts are bounded; the validator re-resolves
  every cited handle to exact immutable source text before accepting a rationale.

## Reviewed implementation slices

1. Strict request/scope/model/final contracts, prompt, and skill.
2. Trusted `assessment.prepare_grade_scope` bridge with ownership and staleness checks.
3. Exact Tool -> readiness/security validator -> Model -> integrity validator playbook.
4. Additive capability registration and architecture/tool-parity gates.

TUT-05C produces only a validated proposal. It does not write the assessment
ledger; TUT-05D owns proof-bound canonical commit.

## Verification

- Schema/prompt/flow unit tests; injection and unknown-evidence fixtures;
  adversarial score/mastery/provider fields; stale rubric checks; scripted-model
  gateway eval; architecture and full offline gates.
