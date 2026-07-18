# Worker Brief: GAP-01 production

## Assignment

Implement the production half of `GAP-01` from
`specs/capability-gap-feedback/README.md` without exposing an agent tool yet.

## Read First

- `docs/decisions/ADR-0011--capability-gap-observation-and-promotion.md`
- `specs/capability-gap-feedback/README.md`
- `specs/capability-gap-feedback/beads/GAP-01-report-contracts-registry.md`
- `src/study_agent/domain/context.py`
- `src/study_agent/playbooks/runtime.py`
- `src/study_agent/adapters/sqlite/run_store.py`
- `src/study_agent/tools/registry.py`

## Scope

You may change:

- `src/study_agent/feedback/__init__.py`
- `src/study_agent/feedback/contracts.py`
- `src/study_agent/feedback/service.py`
- `src/study_agent/feedback/view.py`
- `src/study_agent/ports/capability_gap.py`
- `src/study_agent/adapters/sqlite/capability_gap_store.py`

Do not change:

- Existing files/exports/registries/events/stores except the new files above.
- Course, session, artifact, context, tutor-snapshot, capability, playbook,
  lifecycle, ingestion, prompt, model, CLI, or StudyTool owners.
- Dependencies, configuration, docs/specs, tests, `sbobby-web`, or devkit.

## Requirements

- Define exact closed enums for category, requested operation kind, safe target
  kind, impact kind, limitation kind, verification kind, operational status, and
  workaround status needed by GAP-01 only.
- Persistent/portable contracts contain no free-text field and reject unknown
  fields, bool-as-int, non-canonical arrays/objects, provider selectors, secrets,
  paths, commands, executable payloads, or caller-authored trusted identities.
- `GapKeyV1` is domain-separated SHA-256 over sorted-key canonical UTF-8 JSON
  containing exactly schema version, category, requested-operation kind, safe
  target kind, trusted limitation code, relevant contract identity, and contract
  major. Decode recomputes it; same key/different dimensions fails with stable
  `gap_key_collision`.
- A verified limitation requires a host-trusted failure receipt fingerprint and
  matching contract identity/major. A report without one is explicitly
  `unverified_request` and cannot manufacture a runtime error.
- Define core-derived observation/report identities and a trusted idempotency
  token/fingerprint supplied through service context, never the record payload.
- Exact retry is observationally idempotent. A distinct idempotency identity with
  the same GapKey increments the aggregate exactly once. Store/CAS races and
  process restart converge.
- Define an inward `CapabilityGapStore` protocol and a reference local SQLite
  adapter with schema ownership separate from the course event store. Store only
  structured dimensions, counts/timestamps, fingerprints, lifecycle/export
  status, and resolution metadata allowed by ADR-0011.
- Expose compact aggregate views and exact detail views for trusted hosts. Do not
  expose learner/session/principal identity or add a tool/capability manifest.
- No network, model call, canonical event, Flywheel/devkit/GitHub import, or
  workaround execution.

## Verification

Run the narrowest existing Ruff/mypy/import checks for new production modules,
then relevant architecture/tool-parity and full offline tests if practical.
Finish with `git diff --check`.

## Report Back

Return files changed, exact names, fingerprint domains, SQLite/retry semantics,
verification results, and unresolved mismatches. Explicitly confirm that no
existing file, StudyTool, course event, model, network, devkit, or GitHub behavior
changed. Do not edit tests, commit, or delegate.
