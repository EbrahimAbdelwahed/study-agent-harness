# Log: GAP-04B local PDF-to-Markdown workaround

Date: 2026-07-26 15:42 CEST
Area: capability-gap

## Summary

Implemented the optional local `pypdf==6.14.2` workaround for text-bearing
PDFs. The default harness remains dependency-free. The adapter binds a
host-trusted input/output pair, captures the exact PDF by descriptor, parses
only in a resource-limited worker, renders deterministic loss-marked Markdown,
and publishes without replacing an existing destination. Commit `951cc58`
closes destination-finalization races, recovers deterministic staging links
after interrupted publication, detects Linux inode-reuse rebinding, and
exercises real clean-wheel worker conversion.

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

- Focused local workaround suite: 38 passed, 1 expected macOS containment
  skip.
- Local Ruff on the full repository: passed.
- Local strict mypy: 472 source files, no issues.
- GitHub Actions runs `30218592022` and `30218593481`: all Python 3.12/3.13,
  PDF, recall, Ruff, mypy, clean-wheel, and real-conversion jobs passed; the
  full suite reported 1,806 passed and 12 expected skips per Python lane.

## Notes

- OCR, images, layout reconstruction, native PDF ingestion, network conversion,
  and automatic ingestion remain out of scope.
