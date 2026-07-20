# Worker Brief: GAP-04A production

## Assignment

Implement the provider-neutral allowlisted workaround registry and receipt
contracts from `GAP-04A`; do not add a concrete converter or execute arbitrary
agent-authored instructions.

## Read First

- `docs/decisions/ADR-0011--capability-gap-observation-and-promotion.md`
- `specs/capability-gap-feedback/README.md`
- `specs/capability-gap-feedback/beads/GAP-04A-workaround-registry.md`
- `src/study_agent/cli/registry.py`
- `src/study_agent/capabilities/contracts.py`
- `src/study_agent/domain/context.py`
- `src/study_agent/portability.py`

## Scope

You may change:

- `src/study_agent/workarounds/__init__.py`
- `src/study_agent/workarounds/contracts.py`
- `src/study_agent/workarounds/registry.py`
- `src/study_agent/workarounds/service.py`
- `src/study_agent/ports/workaround.py`

Do not change:

- Existing files/exports/registries, tool/capability manifests, model/playbook/
  prompt owners, ingestion/source adapters, artifact/event/state owners, CLI,
  configuration, dependencies, docs/specs, tests, devkit, or `sbobby-web`.

## Requirements

- Define strict immutable manifests with stable identity/version/fingerprint,
  closed input/output kinds, declared effects, network/credential requirements,
  approval policy, preconditions, limitations, and provenance obligations.
- Define trusted selection/execution receipt values:
  `not_available|requires_approval|attempted_succeeded|attempted_failed`.
  Actual attempted outcomes require an injected executor receipt bound to the
  selected installed manifest; model arguments can never author them.
- Registry is static and host-constructed. Reject duplicate identities,
  provider selectors, shell/command/code fields, package/plugin/install fields,
  remote instructions, arbitrary callable payloads, and undeclared effects.
- Selection searches only installed manifests against closed structured task
  requirements and trusted grants. It returns no match or an exact selected
  manifest/approval requirement; it does not run anything.
- Service execution delegates only through an inward typed `WorkaroundExecutor`
  port selected by trusted host composition. It checks grants/approval/effects,
  preserves immutable input, and requires derived-output digest/provenance plus
  explicit quality limitations before returning success.
- No concrete executor/adapter, network, credential, file converter, shell,
  model call, canonical event, agent loop, dynamic loading, StudyTool, capability,
  Flywheel/devkit/GitHub behavior, or dependency is added.

## Verification

Run focused Ruff/mypy/import checks, relevant portability/architecture/tool
parity, full offline tests if practical, and `git diff --check`.

## Report Back

Return exact contracts/fingerprints, selection/approval/execution semantics,
files and verification results, plus explicit confirmation that no concrete
workaround, dynamic loader, network, StudyTool, or existing file was added.
Do not edit tests, commit, or delegate.
