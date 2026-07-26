# Log: GAP-04B local PDF-to-Markdown workaround

Date: 2026-07-26 15:42 CEST
Area: capability-gap

## Summary

Implemented the optional local `pypdf==6.14.2` workaround for text-bearing
PDFs. The default harness remains dependency-free. The adapter binds a
host-trusted input/output pair, captures the exact PDF by descriptor, parses
only in a resource-limited worker, renders deterministic loss-marked Markdown,
and publishes without replacing an existing destination. Candidate fix commit
The current candidate closes destination-finalization races, recovers deterministic staging
links after interrupted publication, and exercises real clean-wheel worker
conversion; exact post-fix CI evidence is pending.

Security and correctness reviews hardened input and output rebinding,
hardlink/race reconciliation, portable paths, optional-import boundaries, and
truthful platform support. The verified worker-containment implementation is
Linux-only; other platforms fail closed.

## Files Changed

- `pyproject.toml`: added the pinned optional `pdf` extra.
- `src/study_agent/adapters/workarounds/`: added the manifest, filesystem,
  renderer, contained worker, and executor.
- `tests/**/adapters/workarounds/`: added unit, contract, integration,
  architecture, and adversarial coverage.
- `.github/workflows/ci.yml`: added Python 3.12/3.13 real-PDF and clean-wheel
  lanes.
- `docs/decisions/ADR-0013--local-pdf-markdown-workaround.md`: recorded the
  accepted boundary.
- `src/study_agent/adapters/workarounds/filesystem.py`: closed destination
  finalization races and deterministic staging recovery.
- `tests/adversarial/adapters/workarounds/test_executor_filesystem.py`:
  added final-rebind, interrupted-publication, and staging-collision coverage.
- `.github/workflows/ci.yml`: made the clean-wheel PDF lane perform real
  spawned-worker conversion from `/tmp`.

## Verification

- Focused local workaround suite: 42 passed, 1 expected macOS containment skip.
- Local Ruff on the changed surface: passed.
- Local strict mypy on the changed surface: passed.
- Full local suite: 1,795 passed, 13 skipped, with one sandbox-only browser
  socket-bind failure; the same full suite passed in GitHub Actions.
- Exact post-fix GitHub Actions run for the current candidate is pending;
  no post-fix CI result is claimed here.

## Notes

- OCR, images, layout reconstruction, native PDF ingestion, network conversion,
  and automatic ingestion remain out of scope.
