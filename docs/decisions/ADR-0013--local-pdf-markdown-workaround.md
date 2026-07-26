# ADR-0013: Use an optional local pypdf workaround for PDF material

Date: 2026-07-26
Status: Accepted

## Context

The harness intentionally ingests only immutable UTF-8 text and Markdown.
Learners commonly possess text-bearing PDFs, and GAP-03/GAP-04A already expose
an honest unsupported-format report plus a host-authorized workaround boundary.
The user selected PDF-to-Markdown as the first concrete adapter. Native PDF
support, OCR, and a general converter framework would widen the scope. The
earlier proposed ADR-0012 selected HTML and is superseded for GAP-04B.

## Decision

1. Add one optional local adapter using exactly `pypdf==6.14.2`, isolated behind
   the `pdf` installation extra. The provider-neutral core and default runtime
   retain no PDF dependency.
2. The adapter converts only text-bearing PDF bytes to deterministic UTF-8
   Markdown. It does not perform OCR, reconstruct layout, extract images, call a
   network service, or use a model.
3. Execution requires an exact installed manifest grant and host approval. The
   host binds trusted local input/output paths and the expected input digest;
   model-visible task arguments contain no paths.
4. Local reads are descriptor-anchored and race checked. Derived output is
   bounded, private during creation, fsynced, and published without overwrite.
   Parsing always occurs in a worker process with input, IPC, CPU, memory, and
   wall-clock limits applied before importing `pypdf`. There is no in-process
   fallback. A platform that cannot enforce the reference isolation contract
   fails truthfully.
5. If a crash leaves the exact deterministic output at the destination, retry
   reconciles it and returns the same receipt. A differing, symlinked, or
   non-regular destination is a collision and is never overwritten.
6. A successful adapter-specific canonical provenance record binds exact
   input/output digests, manifest and executor fingerprints,
   `pypdf==6.14.2`, renderer policy version, and limitation fingerprint. Its
   hash is the generic receipt's `provenance_fingerprint`.
7. Every derived Markdown file begins with a fixed warning that OCR was not
   performed and that layout, tables, images, equations, and reading order may
   be incomplete. Failures remain truthful and preserve the original
   capability-gap report. The `.md` may later enter the ordinary text ingestion
   service as a separate mechanically derived source; the PDF never becomes a
   native source.

## Consequences

- The common PDF path becomes demonstrable without changing domain state or
  model authority.
- The worker process provides resource containment, not a complete hostile-code
  security sandbox.
- Scanned PDFs and PDFs whose useful meaning is primarily visual remain
  unsupported and require a later, separately approved OCR adapter.
- Layout, tables, reading order, mathematical notation, and image information
  may be lost; this is visible in the output and receipt.
- The optional parser pin requires explicit maintenance and CI coverage.

## Alternatives Considered

- Native PDF ingestion: rejected because it would widen source/event contracts.
- OCR or multimodal extraction: rejected as a separate dependency and safety
  problem.
- External conversion service: rejected because materials should remain local
  and the harness must not gain network or credential effects.
- Shelling out to `pdftotext`: rejected because it adds an undeclared system
  dependency and a broader process boundary.
