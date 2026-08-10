# Plan: GAP-04B local PDF-to-Markdown workaround

Date: 2026-07-26 14:11 CEST
Area: capability-gap

## Goal

Add one explicitly installed, host-authorized PDF-to-Markdown workaround that
preserves exact digest provenance and produces a normal derived Markdown input
without claiming native PDF ingestion.

## Scope

- In scope:
  - optional `pypdf==6.14.2` adapter extra;
  - one closed PDF-to-Markdown manifest;
  - descriptor-anchored local input and atomic no-clobber derived output;
  - bounded deterministic extraction of text-bearing PDFs;
  - truthful receipts for malformed, encrypted, image-only, oversized, timed
    out, or otherwise unsupported PDFs;
  - host approval, quality limitations, provenance, hostile-file tests, package
    and architecture gates.
- Out of scope:
  - OCR, images, tables or layout reconstruction;
  - PDF as a native `SourceKind`;
  - automatic ingestion of the derived file;
  - network, models, shell commands, arbitrary plugins, hosted transport, or
    changes to the seven StudyTools.

## Approved contract

The adapter is installed explicitly from the `pdf` extra. The core and default
wheel import remain dependency-free. The manifest has:

- identity `pdf-to-markdown-pypdf@1`;
- input `pdf`, output `markdown`;
- effects `read_local` and `write_derived`;
- `host_approval`;
- explicit no-OCR and layout/table/image-loss limitations;
- source digest, output digest, parser identity, executor/manifest identities,
  renderer policy, and limitation provenance.

The host pre-binds one approved job to a trusted root, portable `.pdf` input,
portable `.md` output, exact input fingerprint, and approval receipt. Neither
the model nor `WorkaroundTask` receives a path. The executor rejects output
aliases, symlinks, traversal, device files, overwrite attempts, and input
rebinding. It reads at most 16 MiB, requires `%PDF-`, caps page count and output
bytes, and creates the output with a private temporary file plus fsync and an
atomic no-replace publication.

Parsing is isolated in a short-lived worker process with no in-process fallback.
The input bound is enforced before spawn; the child applies CPU and memory
limits before importing `pypdf`; the parent uses bounded IPC plus a wall-clock
deadline followed by terminate, kill, and join. Where those resource controls
are unavailable, the adapter fails closed. This is resource containment, not a
complete security sandbox. The output is canonical UTF-8 Markdown with a fixed,
visible loss/no-OCR warning, document heading, and stable page headings. Empty
or image-only extraction fails truthfully; no OCR fallback is attempted.

Publication is recoverable: an absent destination is staged, fsynced, and
published without replacement; an existing regular destination with the exact
deterministic output is reconciled to the same success receipt; any other
existing entry is a fail-closed collision.

## Approach

1. Record the dependency/effect decision and close the bead's deferred status.
2. Add the adapter-owned contracts, manifest, secure local job binding, isolated
   parser, deterministic renderer, and receipt construction.
3. Add focused parser/receipt tests and independent hostile-filesystem,
   process-loss, timeout, and optional-dependency tests.
4. Run focused tests, Ruff and strict mypy, then the full suite, build, and clean
   wheel imports both without and with the PDF extra.
5. Perform refactor-clean, semantic, architecture, and security review before
   closing the bead.

## Risks

- A pure-Python parser is not itself a hostile-document sandbox; isolation and
  resource enforcement must be real or fail closed.
- PDF text order can differ from visual order. The output and receipt must keep
  this limitation explicit.
- Atomic publication must not overwrite a user file or claim success after
  uncertain process loss.
- Pinning the parser changes the optional dependency surface and must be proven
  on Python 3.12 and 3.13.

## Verification

- Focused GAP-04B unit/contract/integration/adversarial tests.
- `pytest -q`
- `ruff check .`
- strict `mypy`
- wheel build and clean-wheel import without `pypdf`
- wheel install/import and PDF fixture conversion with `[pdf]`
- Python 3.12 and 3.13 GitHub Actions
