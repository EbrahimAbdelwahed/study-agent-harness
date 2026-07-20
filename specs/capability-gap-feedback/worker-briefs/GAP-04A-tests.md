# Worker Brief: GAP-04A tests

## Assignment

Independently pin the generic workaround manifest, registry, authority, receipt,
and provenance boundary from `GAP-04A`.

## Read First

- `docs/decisions/ADR-0011--capability-gap-observation-and-promotion.md`
- `specs/capability-gap-feedback/README.md`
- `specs/capability-gap-feedback/beads/GAP-04A-workaround-registry.md`
- completed GAP-04A production report and changed modules
- existing portability, authority, and architecture tests

## Scope

You may change:

- `tests/unit/workarounds/test_workaround_contracts.py`
- `tests/unit/workarounds/test_workaround_registry.py`
- `tests/unit/workarounds/test_workaround_service.py`
- `tests/architecture/test_workaround_boundaries.py`

Do not change production, existing tests/fixtures, dependencies, configuration,
docs/specs, CLI, devkit, or `sbobby-web`.

## Requirements

- Pin canonical codecs/fingerprints, closed effects/policies/kinds, deterministic
  selection, duplicate rejection, no-match, and explicit approval outcomes.
- Prove uninstalled/ungranted/unapproved strategies cannot be selected or
  reported as attempted; model-authored success/failure is rejected.
- Prove a trusted executor receipt must match manifest identity/version, input
  fingerprint, declared effect, output digest/provenance, and limitation receipt.
- Hostile fixtures cover shell/command/code, callable/executable payload,
  package/plugin/install, remote instruction, hidden network/credential effect,
  provider selector, path traversal, mutable original, missing provenance,
  forged approval, unknown fields, tamper, and non-canonical bytes.
- Architecture tests forbid concrete adapters/converters, filesystem/network/
  HTTP/cloud/provider SDKs, model/prompt/playbook/capability, StudyTool,
  artifact/state/events, dynamic imports, devkit/Flywheel/GitHub, and product UI.

## Verification

Run focused pytest, Ruff, strict mypy, architecture/tool parity, full offline
pytest if practical, and `git diff --check`.

## Report Back

Return files, pinned behaviors, hostile cases, commands/results, and production
mismatches. Confirm production was not edited. Do not commit or delegate.
