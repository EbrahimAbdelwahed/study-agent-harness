# Log: GAP-04B local PDF-to-Markdown workaround

Date: 2026-07-26 15:42 CEST
Area: capability-gap

## Summary

Implemented the optional local `pypdf==6.14.2` workaround for text-bearing
PDFs. The default harness remains dependency-free. The adapter binds a
host-trusted input/output pair, captures the exact PDF by descriptor, parses
only in a resource-limited worker, renders deterministic loss-marked Markdown,
and publishes without replacing an existing destination.

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

## Verification

- Focused local workaround suite: 41 passed, 1 expected macOS containment skip.
- Local Ruff on the changed surface: passed.
- Local strict mypy on the changed surface: passed.
- Full local suite: 1,795 passed, 13 skipped, with one sandbox-only browser
  socket-bind failure; the same full suite passed in GitHub Actions.
- GitHub Actions run 30204462815 on commit
  `2329689b7c7f86646cf65d36365ea78c58b60d79`: all six Python 3.12/3.13 base,
  recall, and PDF jobs passed, including real `pypdf` conversion, Ruff, mypy,
  package builds, and clean-wheel installs.

## Notes

- OCR, images, layout reconstruction, native PDF ingestion, network conversion,
  and automatic ingestion remain out of scope.
