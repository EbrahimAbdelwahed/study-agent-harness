# Worker Brief: PF-06 stale contract tests

## Assignment

Implement Bead `study-agent-harness-integration-0wd` as a tests-only correction
against the already approved PF-06 canonical contracts.

## Goal

Make the eight full-suite capability failures exercise the current public
contract without weakening production validation or restoring the removed
terminated public outcome.

## Allowed files

- `tests/architecture/test_artifact_contract_boundaries.py`
- `tests/architecture/test_artifact_lifecycle_boundaries.py`
- `tests/contract/events/test_kernel_module.py`
- `tests/contract/test_public_capabilities_facade.py`
- `tests/unit/capabilities/test_flashcard_dispatch.py`

## Forbidden files

- `src/**`
- `specs/**`
- `docs/**`
- any gateway implementation or gateway-owned test reserved by another lane
- package metadata, lock files, or generated orchestration state

## Invariants

- Treat Beads as task/completion authority and Agent Mail as coordination and
  reservation authority.
- Do not recursively delegate, merge branches, close beads, delete worktrees,
  or release another worker's reservation.
- Do not change production code.
- Keep the canonical five public capability outcomes; do not re-export
  `TerminatedCapabilityOutcome`.
- Invalid IDs must be tested at a reachable public seam, without bypassing the
  stricter `CapabilityId` constructor accidentally.
- Tampering must be introduced at the serialized or otherwise untrusted seam,
  not through `dataclasses.replace` on a validated immutable value.
- Fingerprint snapshots may change only to the already integrated canonical
  values recorded by the failing suite; explain why the new values are stable.

## Acceptance criteria

- The eight nodes recorded in
  `dev/logs/2026-08-10-0040--package-foundation--integrated-full-suite-triage--log.md`
  pass for the intended semantic reason.
- The focused capability contract suite passes.
- Ruff and strict mypy pass on all owned files.
- `git diff --check` passes.
- The worker commits only the five allowed test files and reports the SHA in
  Agent Mail thread `study-agent-harness-integration-0wd`.

## Verification

```text
uv run --frozen --offline --python 3.13 --extra dev pytest -q tests/architecture/test_artifact_contract_boundaries.py tests/architecture/test_artifact_lifecycle_boundaries.py tests/contract/events/test_kernel_module.py tests/contract/test_public_capabilities_facade.py tests/unit/capabilities/test_flashcard_dispatch.py
uv run --frozen --offline --python 3.13 --extra dev ruff check tests/architecture/test_artifact_contract_boundaries.py tests/architecture/test_artifact_lifecycle_boundaries.py tests/contract/events/test_kernel_module.py tests/contract/test_public_capabilities_facade.py tests/unit/capabilities/test_flashcard_dispatch.py
uv run --frozen --offline --python 3.13 --extra dev mypy --strict tests/architecture/test_artifact_contract_boundaries.py tests/architecture/test_artifact_lifecycle_boundaries.py tests/contract/events/test_kernel_module.py tests/contract/test_public_capabilities_facade.py tests/unit/capabilities/test_flashcard_dispatch.py
git diff --check
```

## Report back

Report files changed, the semantic reason for each correction, exact command
results, commit SHA, and any remaining blocker. Leave the bead open.
