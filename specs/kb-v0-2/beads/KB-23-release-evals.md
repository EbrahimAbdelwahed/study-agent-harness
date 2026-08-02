# KB-23: Release evals, replay proof, and closure

Status: Proposed
Risk: Medium
Depends On: KB-13, KB-16, KB-18, KB-19
Optional Inputs: KB-20, KB-21, KB-22
Parent coverage: §§14–17

## Outcome

KB v0.2 ships only with fixed, versioned evidence that citation integrity,
offline availability, retrieval quality, figure anchoring, incrementality, and
replay satisfy the parent architecture.

## Release evidence

- Retrieval eval by registered-retriever combination, including insufficient
  cases.
- Projection eval comparing structural, lexical, and any model projector.
- At least 100 hand-labeled figures for anchor precision/recall by kind and
  confidence bucket before derived figure work is claimed release-ready.
- Figure retrieval eval for inheritance and direct mode.
- Citation integrity adversarial corpus.
- Two-section incremental-update proof.
- Operational deletion and replay/regeneration proof under KB-00 semantics.

## Acceptance criteria

- [ ] Offline lexical baseline passes with no network, key, model, OCR, vision,
  vector, or reranker installed.
- [ ] Every optional adapter reports its isolated delta and cannot make the
  baseline regress when absent.
- [ ] Citation corruption/tampering never yields silent evidence.
- [ ] Figure anchor precision, not similarity score, governs release claims.
- [ ] Full pytest, Ruff, strict mypy, build, clean-wheel install, architecture,
  security, and semantic review gates are green on the exact commit.
- [ ] Documentation names limitations and degradation truthfully.
- [ ] All completed beads, ADRs, migration notes, and next-version deferrals are
  reflected in the parent spec before closure.

## Verification

- CI-owned full suite and optional adapter matrices.
- Independent review of eval fixtures, leakage, target construction, and
  non-vacuous assertions.
- Manual inspection of representative medical search, exact citation,
  superseded citation, outline, figure attachment, and lineage.

## Out of scope

- Product UI, hosted deployment, submission/demo assets, or claiming optional
  adapter quality without its gate.
