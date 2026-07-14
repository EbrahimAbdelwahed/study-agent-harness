# Review Report: Agent-managed lifecycle plan and apply

Date: 2026-07-14
Reviewers: semantic reviewer, architecture reviewer, security reviewer

## Findings

- [P1, closed] Returning from source revision B to historical revision A was
  initially non-convergent. The ingestion owner now records an explicit,
  replayable revision-selection event without rewriting or duplicating blobs.
- [P1, closed] Expected-sequence course creation could reconcile an identical
  concurrent winner as success. Explicit CAS now reports that race as retryable.
- [P1, closed] Apply receipts could mix actions from the authorized and freshly
  observed plans. Receipts now preserve authorized actions and enforce ordered,
  globally unique action ordinals across disjoint categories.
- [P1, closed] Writable SQLite initially reopened lexical repository paths after
  safe observation. The reference CLI now retains the inspected owner, pins the
  state directory, creates database entries no-follow, and verifies the live
  SQLite descriptor identity before the first write. Root, state, config,
  symlink, and regular A→B→A replacement tests leave external targets unchanged.
- [P1, closed] Canonical source-integrity and ordinary SQLite failures could
  escape the machine-clean CLI boundary. They now map to redacted operational
  failures; binding races remain distinct retryable conflicts.
- [P2, closed] `LifecycleAuthority` now carries the correlation identity supplied
  by the trusted host, and receipt status/category invariants reject contradictory
  evidence.

## Required Fixes

- None remaining.

## Verification

- Python 3.12: 772 passed, 2 declared skips; Ruff and strict mypy green across
  195 source files.
- Python 3.13 isolated: 773 passed, one opt-in network smoke skipped; Ruff and
  strict mypy green.
- Security focus: 117 tests passed; 22 repeated lifecycle cycles kept live file
  descriptors stable.
- Wheel and source distribution 0.2.0 built successfully; clean-wheel smoke
  reported the expected harness version and operation contract.
- `git diff --check`: passed.

## Architecture Notes

- Domain events remain canonical; lifecycle manifests, plans, receipts, and
  indexes remain operational evidence.
- Course and ingestion mutations continue through their existing service owners
  and expected-sequence boundaries. Retrieval remains rebuildable and
  discardable.
- The management plane remains separate from the exact seven model-facing
  StudyTools. Skills/playbooks and model-adapter responsibilities are unchanged.
- The filesystem working-directory pin is confined to the serial reference CLI.
  The model-agnostic lifecycle core depends only on an injected runtime boundary.

## Residual Risks

- Hosts that perform concurrent relative-path I/O must isolate the reference
  CLI runtime or provide another `LifecycleRuntime`; the CLI mutation scope is
  process-global and cooperative.
- Platforms without `/dev/fd` or `/proc/self/fd` fail closed for lifecycle
  mutation because the standard-library SQLite binding does not expose its file
  descriptor directly.

## Verdict

Approved after semantic, architecture, and security re-review. No P0–P2
findings remain.
