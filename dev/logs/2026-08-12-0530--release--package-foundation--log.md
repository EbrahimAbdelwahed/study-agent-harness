# Log: Package Foundation 0.3.0 release gate

Date: 2026-08-12 05:30
Area: release

## Summary

Prepared the exact local `study-agent-harness==0.3.0` adoption artifact for
Cardine. The release workflow builds one wheel/sdist pair and verifies that same
pair on Python 3.12 and 3.13. No tag, remote upload, or online release occurred.

The full release gate exposed stale PF-05 replay fixtures and two concrete
replay defects. Historical `DomainEvent` values now use exact-schema decoding
and reduction, projected chunks are reconstructed in canonical ordinal order,
and projection JSON rejects duplicate object keys.

## Artifact Evidence

- Directory: `/tmp/study-agent-harness-package-foundation-release-approved`
- Wheel: `study_agent_harness-0.3.0-py3-none-any.whl`
- Wheel SHA-256: `2db066fda85f605fe7e284444192f59a198b34ec5e7fe993a63e21efbdc0a5a0`
- Source distribution: `study_agent_harness-0.3.0.tar.gz`
- Source distribution SHA-256: `dcdea4977ba6835f442c61cd62c326282f29c5c70d7e2c4db9852fd13734a055`

## Verification

- `uv build --out-dir /tmp/study-agent-harness-package-foundation-release-approved`: passed; one wheel and one source distribution built.
- `python scripts/release/check_distribution.py <dist>`: passed on Python 3.12.12 and 3.13.12.
- `python scripts/release/check_public_facade.py <dist>`: passed on Python 3.12.12 and 3.13.12; manifest fingerprint `04d7ad70fcd279ee77f3aeb1e3fc9e16ebfad41b9796bbe9ff2cf13d9199c76c`.
- `python scripts/release/check_side_by_side.py <dist>`: passed on Python 3.12.12 and 3.13.12; positive Cardine-only fixture installed and copied-core collision was rejected.
- `python -m pytest -qq`: Python 3.12 passed with 2583 tests and 14 optional skips; Python 3.13 exited zero with the same required offline surface.
- `python -m ruff check src tests scripts/release`: passed.
- `python -m mypy`: passed for 585 source/test files.
- `git diff --check`: passed.

## Notes

- Optional live-provider, PDF-extra, and FSRS-extra cases remain opt-in and did
  not weaken the dependency-free release gate.
- PF-11 remains the only stable `1.0.0` promotion gate after Cardine CA-08
  installed-parity evidence.
