# Task Bead: PF-11 Stable facade promotion

Status: Open
Priority: P2
Type: task
Depends On: PF-10, CA-08-installed-parity-evidence

## Outcome

An executable Harness-only gate verifies signed and hashed PF-10 artifacts plus
an external CA-08 installed-parity report and writes one idempotent
`0.3.0`-to-`1.0.0` facade-promotion record without importing or testing Cardine.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-11 evidence envelope, signature/hash checks, version transition, idempotency, negative vectors, and Harness-only boundary in `specs/package-foundation/slices/PF-11-stable-facade-promotion.md`.
- README post-adoption PF-11 gate and no-runtime-behavior criteria.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/slices/PF-11-stable-facade-promotion.md`.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `cli-release-test-worker`

Rationale:

This is an executable release-evidence command with canonical JSON, artifact
hashing, clean failure behavior, and focused smoke tests, matching the release
profile.

## Context

Stable facade compatibility is earned only after PF-10 and an externally
produced CA-08 installed-parity report. The gate validates immutable evidence
and records promotion outside domain state; it adds no runtime symbols.

## Invariants

- CA-08 report has exactly the approved schema fields, producer `CA-08`, passed status, Python 3.12/3.13 rows, facade ownership, and no duplicate package owner.
- Wheel, sdist, and report SHA-256 values are recomputed from bytes; detached signature is checked through declared trusted input; unknown fields and mismatches fail closed.
- Success writes `from_version=0.3.0`, `to_version=1.0.0`, hashes, key ID, timestamp, and verifier version as one canonical external record.
- Promotion is idempotent by report/wheel/sdist hashes plus target; changed bytes or target cannot overwrite an existing record.
- Tests and scripts use synthetic evidence and standard-library tooling only; no Cardine import, path, package, or test dependency appears.

## What To Do

- Implement canonical CA-08 evidence parsing, strict field validation, hash recomputation, detached-signature verifier port, and promotion record codec.
- Implement the executable promotion command with atomic no-write-on-failure and same-tuple idempotency.
- Add synthetic signed/hashed positive, missing-field, hash, signature, version, matrix, and duplicate-byte fixtures.
- Add import scan and help smoke proving Harness-only release tooling.

## Likely Allowed Files / Packages

- `scripts/release/promote_stable_facade.py`, `scripts/release/compatibility_evidence.py`.
- `tests/quality/test_stable_facade_promotion.py`.
- `tests/fixtures/release/ca08-installed-parity.json`, detached signature, and trust-input fixture.
- One factual `dev/logs/...stable-facade-promotion...` file if implementation evidence requires it.

## Acceptance Criteria

- [ ] Positive command verifies PF-10 `0.3.0` wheel/sdist hashes and signed CA-08 report, then writes canonical `1.0.0` record.
- [ ] Unknown fields, missing rows, failed parity, stale versions, changed artifact/report bytes, unsigned evidence, and invalid signatures exit nonzero and write nothing.
- [ ] Repeating the same evidence tuple returns the same record; any changed tuple cannot overwrite it.
- [ ] Command help, focused tests, and import scan pass with no Cardine text dependency in implementation/tests.
- [ ] No public API, schema, runtime behavior, dependency, or temporary local-path shortcut is added outside the evidence gate.

## Verification

- `uv run --python 3.13 --extra dev pytest -q tests/quality/test_stable_facade_promotion.py`: positive and negative vectors pass.
- `uv run --python 3.13 --extra dev python scripts/release/promote_stable_facade.py --help`: executable help succeeds.
- `uv run --python 3.13 --extra dev python scripts/release/promote_stable_facade.py --artifacts /tmp/pf10-0.3.0 --report tests/fixtures/release/ca08-installed-parity.json --signature tests/fixtures/release/ca08-installed-parity.json.sig --trust-input tests/fixtures/release/ca08-trust-input.json --output /tmp/facade-promotion-1.0.0.json`: positive promotion writes the record.
- `uv run --python 3.13 --extra dev python -c "import pathlib; p=pathlib.Path('tests/quality/test_stable_facade_promotion.py'); assert 'cardine' not in p.read_text().lower()"`: import scan passes.
- `git diff --check`: no whitespace errors.

## Out Of Scope

- New symbols or schemas, runtime changes, Cardine migration/co-install/parity, source checkout evidence, unsigned artifacts, and publication credentials.

## Removal Conditions

- None. This is the permanent evidence gate for promotion; local-path and unsigned-fixture shortcuts are forbidden from acceptance.

