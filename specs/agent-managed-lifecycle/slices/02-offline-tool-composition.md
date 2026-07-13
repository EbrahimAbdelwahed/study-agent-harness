# Slice 02: Offline tool composition

Release: 0.1.1
Depends on: slice 01
Status: Complete (2026-07-13)

## Contract unlocked

An offline repository can enumerate and invoke applicable read/session tools
without a configured model. Only `grounding.ask` resolves model configuration.

## API seam

- `LocalRepository.study_tools(course_id)` composes the same exact-seven
  registry with a lazy `GroundingAskService` provider.
- `GroundingAskTool` resolves that provider only during its own invocation.
- Missing model configuration is translated by the lazy provider into the
  existing portable `GroundingAskError(INCOMPATIBLE_RUNTIME)` before the registry
  boundary. No `study_agent.cli` exception or provider detail reaches tools or
  application code.

This is dependency construction only. The existing grounding service, skill,
playbook, prompt, validators, pins, and adapter remain the sole behavior path.

## Runnable checkpoint

Open an offline repository, enumerate seven manifests, invoke `course.get`,
`source.list`, `source.search`, `citation.resolve`, `session.get_context`, and
`session.record_note` as their preconditions allow, then show that only
`grounding.ask` reports model unavailability.

## Verification

- Regression test reproduces the current offline `study_tools()` failure before
  the fix.
- Socket-denial and empty-environment tests prove offline composition.
- Tool fingerprint snapshot stays byte-identical.
- Missing-model ask creates no run row or domain event.
- Scripted-model parity across direct service, harness, tool registry, and CLI
  remains unchanged.
- Registry access does not rebuild retrieval merely to list manifests.
- Architecture tests forbid imports from `study_agent.cli` into tools,
  application, domain, or ports.

## Human review checkpoint

Inspect the composition boundary and error mapping. Reject any solution that
branches on provider/model name or duplicates grounding behavior.
