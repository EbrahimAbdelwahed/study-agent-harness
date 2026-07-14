# Task Bead: TUT-03A capability contracts and discovery

Status: Ready
Priority: P0
Type: tracer-bullet
Depends On: TUT-02

## Outcome

An external tutor host can discover a closed, deterministic set of trusted
capability manifests without importing a model SDK, selecting a provider, or
changing the seven-tool `agent-operations@1` contract.

## Acceptance Criteria

- [ ] Public v1 values cover identity/version, schemas, lifecycle support,
  required authority, and the closed outcome-status vocabulary.
- [ ] Discovery is sorted, immutable, duplicate-rejecting, and limited to
  composition-root-registered trusted capabilities.
- [ ] Manifests reject model/provider selectors and invalid JSON schemas.
- [ ] `explain_concept@1` and `assess_understanding@1` identities are reserved,
  but no model behavior or next-action policy is introduced.
- [ ] Existing StudyTool manifests and fingerprints remain exact.

## Verification

- Contract/value tests, tool parity, architecture checks, and full gates.

## Out Of Scope

- Execution/resume/cancellation, playbooks/prompts, model adapters, UI, and
  canonical writes.
