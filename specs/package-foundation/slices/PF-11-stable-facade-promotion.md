# PF-11 — Stable facade promotion

## Outcome

After PF-10 publishes the exact `0.3.0` adoption artifact and downstream CA-08
reports installed parity, an executable Harness-only gate promotes the curated
facade to `1.0.0`. The gate consumes signed/hashed compatibility evidence and
does not import Cardine, inspect a Cardine checkout, or add a Cardine test
dependency.

## Non-goals

- No new public symbol, schema, runtime behavior, or dependency.
- No Cardine source migration, co-install implementation, or Cardine test
  execution; actual co-install/parity remains CA-04/CA-10-owned.
- No promotion from a source checkout, unsigned report, mutable artifact, or
  evidence that omits the installed wheel/sdist hashes.

## Exact contracts

- `scripts/release/promote_stable_facade.py` is an executable command. It
  accepts a PF-10 `0.3.0` wheel/sdist directory, one CA-08 installed-parity
  report, a detached report signature, and a declared trusted verification
  input. It exits non-zero and writes no promotion record unless every input
  is present and valid.
- The CA-08 report is a canonical JSON envelope with exactly these evidence
  fields: `schema_version`, `producer_id` (`CA-08`), `harness_version`,
  `python_versions`, `wheel_sha256`, `sdist_sha256`, `installed_imports`,
  `entry_points`, `base_dependencies`, `parity_status`, `report_sha256`, and
  `signature_key_id`. `parity_status` must be `passed`; the matrix must cover
  Python 3.12 and 3.13; and the installed import/entry-point assertions must
  identify the curated facade and no duplicate `study_agent` owner.
- Verification recomputes the report, wheel, and sdist SHA-256 values,
  checks the detached signature through the injected/declared trust input,
  and rejects unknown fields, mismatched versions, missing interpreter rows,
  failed parity, or changed bytes. No raw source, principal, credential, or
  answer content is accepted as evidence.
- A successful run writes one canonical `FacadePromotionRecord` containing
  `from_version=0.3.0`, `to_version=1.0.0`, report/artifact hashes,
  `signature_key_id`, verification timestamp, and the verifier version. The
  record is an external release artifact; it is not a domain event or runtime
  store entry.
- Promotion is idempotent by the tuple of report hash, wheel hash, sdist hash,
  and target version. Repeating the same tuple returns the same record; any
  differing byte or target fails closed and cannot overwrite an earlier
  record.
- PF-11 tests use a synthetic signed/hashed report fixture and artifact bytes
  only. They import Harness release helpers and standard-library tooling; no
  test imports `cardine`, references a Cardine path, or runs Cardine code.

## Probable files

- `scripts/release/promote_stable_facade.py` — evidence validation and record
  writer.
- `scripts/release/compatibility_evidence.py` — canonical envelope, hash, and
  injected signature-verifier port.
- `tests/quality/test_stable_facade_promotion.py` — executable positive,
  missing-field, hash-mismatch, signature, and idempotency vectors.
- `tests/fixtures/release/ca08-installed-parity.json` and its detached
  signature fixture — synthetic evidence with no Cardine import dependency.
- `dev/logs/YYYY-MM-DD-HHMM--release--stable-facade-promotion--log.md` —
  factual command and artifact-hash results for the implementation pass.

## Dependencies

PF-10 `0.3.0` artifact and release evidence; an externally produced, signed
and hashed CA-08 installed-parity report. This is a release-orchestration
dependency only: PF-11 source and tests have no Cardine import, path, package,
or test dependency.

## Removal conditions

None. PF-11 is the permanent evidence gate for the `0.x` to `1.0.0` facade
promotion. Temporary local-path or unsigned-fixture shortcuts are forbidden
from the accepted implementation.

## Review surface

Inspect canonical JSON ordering, detached-signature verification, all three
artifact/report hash comparisons, exact version transition, idempotent record
handling, and the import scan proving no Cardine dependency.

## Exact verification

```text
uv run --python 3.13 --extra dev pytest -q tests/quality/test_stable_facade_promotion.py
uv run --python 3.13 --extra dev python scripts/release/promote_stable_facade.py --help
uv run --python 3.13 --extra dev python scripts/release/promote_stable_facade.py --artifacts /tmp/pf10-0.3.0 --report tests/fixtures/release/ca08-installed-parity.json --signature tests/fixtures/release/ca08-installed-parity.json.sig --trust-input tests/fixtures/release/ca08-trust-input.json --output /tmp/facade-promotion-1.0.0.json
uv run --python 3.13 --extra dev python -c "import pathlib; p=pathlib.Path('tests/quality/test_stable_facade_promotion.py'); assert 'cardine' not in p.read_text().lower()"
git diff --check
```

The positive command must produce a canonical `1.0.0` record. Negative vectors
must prove that unsigned, tampered, stale-version, incomplete-matrix, and
duplicate-byte evidence is rejected without modifying an existing record.

## Definition of done

- PF-10 `0.3.0` artifact hashes and CA-08 installed-parity hashes are verified
  from canonical signed evidence.
- A successful, idempotent command writes the exact `0.3.0 -> 1.0.0`
  promotion record; failures write nothing and never overwrite prior evidence.
- The implementation and its tests have no Cardine import, source-path, or
  test dependency and introduce no dependency or public API change.
- Focused positive/negative tests, executable command smoke, import scan, and
  `git diff --check` pass.
