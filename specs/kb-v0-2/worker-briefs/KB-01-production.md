# Worker Brief: KB-01 production

## Goal

Implement only the frozen normalized-text substrate contracts, exact identity,
page-map validation, `source.substrate_produced@1` codec/reducer, and trusted
application seam defined by KB-01 and ADR-0014.

## Worker Profile

Use `knowledge-base-core-worker`.

## Allowed Files

- `src/study_agent/domain/identifiers.py`
- `src/study_agent/domain/substrate.py`
- `src/study_agent/ingestion/substrate.py`
- `src/study_agent/ingestion/substrate_events.py`
- `src/study_agent/ingestion/substrate_projection.py`
- additive substrate reduction/registration in
  `src/study_agent/ingestion/projection.py`
- additive exports in the directly owning `__init__.py` files

## Forbidden Files

- Tests, existing v0.1 source/chunk/citation/event payload shapes, FTS,
  connectors, tree/unit/search code, CLI, export, skills/playbooks, model or
  provider adapters, dependencies, CI, and unrelated docs.

## Required Contracts

- `SubstrateId` is the SHA-256 of exact frozen normalized UTF-8 bytes.
- Do not construct or redefine v0.2 `revision_id`; KB-02 owns its exact
  manifest and canonical encoding.
- `SubstrateId` and production IDs use the exact namespace, domain separator,
  canonical JSON encoding, and identity-bearing fields in ADR-0014.
- A substrate is non-empty normalized UTF-8. Pagination is either absent
  (`page_count=None`, empty map) or present with positive `page_count`, an
  offset-zero first entry, strictly increasing in-bounds Unicode-code-point
  offsets, and strictly increasing positive page numbers bounded by the count.
- The service accepts trusted blob/converter receipts and verifies bytes and
  hashes before append. Both receipts bind source and original blob; only
  service authority may append. Raw blob references and human/model authority
  are rejected.
- Repeated exact identity-bearing production is idempotent and retains the
  first committed timestamp. Converter, normalization, admission, page-map
  policy, or page-map changes create a new production; byte changes create a
  new substrate.
- The v0.1 normalized blob has a deterministic legacy-substrate mapping in the
  existing source-event reducer/registration path without rewriting or adding
  events and without changing append behavior.

## Verification

- Ruff and strict mypy on allowed production files.
- Relevant existing ingestion/event/replay/import-boundary tests.
- `git diff --check`.

## Report

Report exact public values/events, identity inputs, reducer state shape, legacy
mapping, validation boundaries, and commands/results. Do not edit tests,
commit, push, or delegate.
