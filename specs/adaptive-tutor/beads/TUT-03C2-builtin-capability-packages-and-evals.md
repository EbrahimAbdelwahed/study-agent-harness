# Task Bead: TUT-03C2 built-in capability packages and evals

Status: Ready
Priority: P0
Type: expand
Depends On: TUT-03C1

## Outcome

Trusted portable `explain_concept@1` and `assess_understanding@1` packages use
the gateway and optional dialogue primitive with deterministic offline evals.

## Acceptance Criteria

- [ ] Manifests, skills, playbooks, prompts, validators, pins, and dependency
  resolvers are closed, versioned, provider-free, and composition-root owned.
- [ ] Sufficient evidence acts directly; bounded ambiguity asks exactly one
  material clarification; insufficient/conflicting evidence terminates before
  dialogue or model execution.
- [ ] Explanation returns an evidence-grounded teaching result. Assessment
  returns questions only; attempts, grading, mastery, and scheduling are absent.
- [ ] State-write policies are empty and packages cannot register or mutate the
  seven public StudyTools.
- [ ] Scripted-model evals cover direct, clarification, resume, changed input,
  interruption, unsupported evidence, and prompt-injection-shaped evidence.

## Verification

- Package contracts, gateway/playbook integration, scripted-model evals,
  architecture/tool parity, and full offline gates.
