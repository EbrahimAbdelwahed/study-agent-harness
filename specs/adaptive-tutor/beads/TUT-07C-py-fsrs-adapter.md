# Task Bead: TUT-07C optional py-fsrs adapter

Status: Done — optional py-fsrs adapter and 3.12/3.13 CI lane verified 2026-07-24
Priority: P1
Type: expand
Depends On: TUT-07B

## Outcome

One optional adapter implements the provider-neutral scheduler port with the
publicly maintained `fsrs==6.3.1` package while keeping package types and
defaults outside canonical state.

## Acceptance Criteria

- [x] Add `recall = ["fsrs==6.3.1"]` as an optional dependency only after a
  clean Python 3.12/3.13 install, import, license metadata, and API smoke pass.
  Base installation and all inward imports remain functional without it.
- [x] All `fsrs` imports and conversions live under a scheduling adapter
  package. Domain, ports, recall events/reducers/service/views, skills,
  playbooks, tools, application owners, and exporters never import it.
- [x] The adapter constructs the scheduler with explicit reviewed configuration
  rather than unpinned library defaults; its policy fingerprint covers every
  effective parameter and stable adapter policy version.
- [x] Adapter receipts report exact `implementation_id = "py-fsrs"` and
  `implementation_version = "6.3.1"`; an unexpected installed version fails
  closed before any canonical write.
- [x] The adapter reconstructs scheduling from the complete core history in
  deterministic order. Serialized `Card`, `ReviewLog`, opaque package state,
  random/fuzzed scheduling, and library object representations never become
  canonical inputs or outputs.
- [x] Core ratings map explicitly and exhaustively to the package rating enum;
  timezone-aware UTC conversion and due output normalization are pinned.
- [x] Conformance fixtures compare the fake and FSRS implementations only on
  port invariants, while adapter-specific golden fixtures pin expected due
  decisions for empty, failed, hard, good, easy, and mixed histories.
- [x] If package API or deterministic behavior cannot satisfy these gates
  without leaking implementation state, stop with evidence and retain the
  working provider-neutral fake policy rather than weakening the seam.

## Verification

- Clean optional-extra install/import/API smoke; adapter unit/golden and port
  conformance tests; missing/wrong-version negatives; base-wheel smoke without
  FSRS; Python 3.12/3.13, Ruff, strict mypy, full offline gates.
