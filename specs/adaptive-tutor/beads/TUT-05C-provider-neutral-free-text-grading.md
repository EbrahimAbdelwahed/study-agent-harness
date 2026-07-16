# Task Bead: TUT-05C provider-neutral free-text grading

Status: Blocked on TUT-05B
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
- [ ] Model output is a strict `graded | needs_review | ungradable` union. Every
  ordered rubric criterion appears exactly once with `met | not_met | uncertain`,
  a bounded rationale, evidence handles, and bounded confidence.
- [ ] The integrity validator derives status and score from criterion outcomes;
  it never trusts a model-authored score. Unknown evidence, missing/duplicate
  criteria, stale rubric fingerprints, unsupported claims, or malformed output
  become `needs_review`/`ungradable` or terminate without fabricating a grade.
- [ ] Evidence handles resolve only through the immutable assessment artifact
  provenance and canonical source content.
- [ ] Prompt, skill, playbook, validator, and capability versions are pinned;
  the same behavior runs with scripted or generic model adapters and does not
  expand the seven public StudyTools.

## Verification

- Schema/prompt/flow unit tests; injection and unknown-evidence fixtures;
  adversarial score/mastery/provider fields; stale rubric checks; scripted-model
  gateway eval; architecture and full offline gates.
