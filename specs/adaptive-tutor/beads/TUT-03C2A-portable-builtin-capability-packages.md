# Task Bead: TUT-03C2A portable built-in capability packages

Status: Done
Priority: P0
Type: tracer-bullet
Depends On: TUT-03C1

## Outcome

The repository exposes closed, provider-free `explain_concept@1` and
`assess_understanding@1` package definitions that a trusted composition root
can bind to request-scoped tools, validators, prompts, and read dependencies.

## Acceptance Criteria

- [x] Each package has one closed manifest, skill, linear playbook, prompt,
  output schema, pins, and binding factory with no provider/model selector.
- [x] Both flows search trusted sources first, terminate on insufficient or
  conflicting evidence, derive clarification need in a validator, and use one
  validator-gated dialogue before exactly one model call.
- [x] Explanation returns a citation-resolved teaching answer; assessment
  returns questions only, with no answer key, attempt, grade, mastery, schedule,
  or state writes.
- [x] Package wiring is composition-root owned and reuses the private
  `source.search@1` executor contract without changing the seven StudyTools.
- [x] Definitions and validators reject unknown evidence handles, malformed
  outputs, prompt injection as authority, and provider-selecting content.

## Verification

- Package/validator contract tests, architecture and tool parity, Ruff, strict
  mypy, and focused offline tests.
