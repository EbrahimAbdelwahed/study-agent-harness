# Worker Brief: PF-11

## Assignment

Implement `PF-11` from `specs/package-foundation/slices/PF-11-stable-facade-promotion.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, and `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, PF-10/PF-11 slices, and `specs/package-foundation/beads/PF-11-stable-facade-promotion.md`
- existing release scripts, fixture conventions, and standard-library hash/signature helpers

## Scope

You may change:

- `scripts/release/promote_stable_facade.py`, `scripts/release/compatibility_evidence.py`
- `tests/quality/test_stable_facade_promotion.py`
- the three named release evidence fixtures and one factual stable-facade promotion log if needed

Do not change:

- Package specs, slices, beads, briefs, runtime/domain/public API behavior, dependencies, product source/path/package/tests, publication credentials, or source-checkout shortcuts

## Invariants and Requirements

- Parse the exact CA-08 envelope with producer `CA-08`, passed parity, 3.12/3.13 rows, facade ownership, no duplicate owner, and no unknown fields.
- Recompute report, wheel, and sdist SHA-256 values and verify detached signature through declared trust input before writing anything.
- Success writes one external record with exact `0.3.0` to `1.0.0`, hashes, key ID, timestamp, and verifier version; same tuple retries return the same record.
- Missing, tampered, unsigned, stale, incomplete, failed, or changed evidence exits nonzero and never overwrites an existing record.
- Implementation/tests use synthetic evidence and standard-library tooling only and contain no product import/path/test dependency.

## Verification

Run:

```bash
uv run --python 3.13 --extra dev pytest -q tests/quality/test_stable_facade_promotion.py
uv run --python 3.13 --extra dev python scripts/release/promote_stable_facade.py --help
uv run --python 3.13 --extra dev python scripts/release/promote_stable_facade.py --artifacts /tmp/pf10-0.3.0 --report tests/fixtures/release/ca08-installed-parity.json --signature tests/fixtures/release/ca08-installed-parity.json.sig --trust-input tests/fixtures/release/ca08-trust-input.json --output /tmp/facade-promotion-1.0.0.json
uv run --python 3.13 --extra dev python -c "import pathlib; p=pathlib.Path('tests/quality/test_stable_facade_promotion.py'); assert 'cardine' not in p.read_text().lower()"
git diff --check
```

## Report Back

Return files changed, evidence parsing/hash/signature/idempotency behavior,
exact verification, profile constraints followed, unresolved questions, and follow-up beads.
