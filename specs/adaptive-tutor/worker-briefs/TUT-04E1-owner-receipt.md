# Worker Brief: TUT-04E1 generated-batch owner receipt

## Goal

Add the durable, provider-neutral ownership locator that lets a later verified
artifact adapter recover the exact lesson page or exam analysis responsible for
one completed child run. This slice does not convert or commit artifacts.

## Interface

- `GeneratedBatchOwnerStore.create(child_run_id, payload)` atomically claims the
  sole slot for a child run; `load(child_run_id)` performs exact-key lookup.
- `GeneratedBatchOwnerRegistry` accepts only strict lesson-page or exam-analysis
  receipts. Exact retry returns the existing receipt; another payload conflicts.
- There is no list, scan, reverse lookup, filesystem, database, model, gateway,
  or canonical-event dependency at this seam.

## Receipt invariants

- Both variants bind the exact child run, task, completed B1 receipt, and B1A
  proof fingerprints.
- Lesson receipts bind the parent lesson run and coordinator, request, plan,
  profile, canonical bundle order and page position, bundle, prepared wrapper,
  scope, retrieval read set, and source-revision commitments. Optional
  cross-page overview association is explicit, fingerprinted, and must point to
  an earlier bundle; it never becomes a same-batch parent ordinal.
- Exam receipts retain the exact canonical `ExamAnalysisRequest` bytes and only
  a fingerprint of the opaque request key. They also bind prepared scope,
  redacted prompt projection, evidence mapping, coordinator, and child proof.
- The exam request contract is structurally checked here to avoid an artifacts
  → exams import cycle. The later verified adapter must decode it through
  `ExamAnalysisRequest.from_bytes` before proof recovery.

## Out of scope

- Artifact candidate conversion, provenance assembly, proof loading, source or
  media re-resolution, coordinator publication, runtime composition, and event
  writes.

## Verification

- Canonical round-trip and strict-field tests for both variants.
- Page-order/association, exact request bytes, tamper, slot-key mismatch, exact
  retry, and competing-owner conflict tests.
- Architecture test for the two-file seam and provider/filesystem isolation.
- Ruff, strict mypy, and focused pytest.
