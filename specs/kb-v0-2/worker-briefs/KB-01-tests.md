# Worker Brief: KB-01 tests

## Goal

Independently pin KB-01 substrate identity, strict codecs, trusted provenance,
page-map boundaries, idempotency, legacy mapping, append conflicts, corruption,
and byte-identical replay.

## Worker Profile

Use `knowledge-base-core-worker`.

## Allowed Files

- `tests/unit/knowledge/test_substrate_contracts.py`
- `tests/unit/knowledge/test_substrate_events.py`
- `tests/unit/knowledge/test_substrate_projection.py`
- `tests/integration/test_substrate_production.py`
- `tests/integration/test_substrate_replay.py`
- `tests/architecture/test_knowledge_boundaries.py`

## Forbidden Files

- All production files, other tests, specs/docs, CLI/export, adapters beyond
  test fixtures, dependencies, CI, providers, models, skills, and playbooks.

## Acceptance Criteria

- Golden identities pin the substrate namespace and the domain-separated
  canonical production encoding. Revision identity is explicitly absent.
- Strict codecs reject missing/extra fields, bool-as-int, invalid UTF-8,
  forged hashes/IDs, bad blob bindings, invalid timestamps, and malformed page
  maps.
- Page maps pin absent pagination and reject empty-present maps, negative,
  duplicate, descending, and out-of-bounds offsets, non-positive/descending
  pages, and pages beyond `page_count`.
- Exact retry retains the first timestamp; policy/page-map reconversion retains
  both production receipts, while byte changes also create a new substrate.
- Blob mismatch, orphan blob, append conflict, and projection corruption fail
  closed.
- Deleting the read projection and replaying canonical events reproduces exact
  canonical bytes.
- A v0.1 source event maps deterministically to a legacy substrate without
  rewriting the event or changing existing v0.1 behavior.
- Architecture tests exclude SQLite/provider/model/connector imports from
  domain contracts and prevent a parallel byte owner.

## Verification

- New focused tests.
- Existing ingestion, blob-store, event-store, source projection, retrieval,
  export, Ruff, strict mypy, and `git diff --check`.

## Report

Return concrete semantic mismatches as findings. Do not edit production,
commit, push, or delegate.
