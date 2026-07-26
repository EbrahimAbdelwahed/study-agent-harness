# KB-20: Optional OCR figure-label adapter

Status: Proposed — dependency decision required
Risk: High
Depends On: KB-17C, KB-18
Parent coverage: §§9.3–9.4, 14; M8

## Outcome

A separately approved, sandboxed OCR adapter produces bounded non-citable
`FigureLabels` that improve rare-token lexical search without affecting figure
identity, anchors, or offline correctness.

## API seam

- Provider-neutral OCR port/receipt and `FigureLabels` derived artifact.
- Adapter manifest declares dependency/version, supported media, containment,
  resource limits, and capability availability.
- Labels feed figure projection terms through KB-08/09; raw OCR output never
  becomes canonical evidence.

## Acceptance criteria

- [ ] Dependency, license, platform support, sandbox, image limits, timeout,
  memory/CPU limits, and hostile-image behavior receive explicit approval.
- [ ] Missing OCR capability preserves caption/inheritance retrieval.
- [ ] Artifact identity binds figure hash, adapter/version, configuration, and
  exact output.
- [ ] OCR failure is typed and cannot mutate anchors or citations.
- [ ] Labels are bounded, normalized, injection-safe, visibly derived, and
  invalidatable.
- [ ] Figure retrieval eval demonstrates measured precision/recall delta.

## Verification

- Adapter contract and clean optional-install CI lane.
- Hostile/corrupt/oversized image, timeout, determinism, provenance, and
  degradation tests.
- Security and dependency review.

## Out of scope

- Vision captions, image embeddings, or making OCR a core dependency.
