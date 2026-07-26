# KB-15C: Derived study-material profile and conformance doctor

Status: Proposed
Risk: Medium
Depends On: KB-02, KB-07, KB-14, KB-15A
Parent: KB-15

## Outcome

The Appendix A dialect maps deterministically to generic KB regions and an
explicit promotion/lineage act, while `doctor` makes real corpus drift visible.

## Acceptance criteria

- [ ] Headings/anchors, emphasis callouts, recap bullets, tables, figure
  markers, chemical markers, uncertainty flags, and visual markup follow
  Appendix A exactly.
- [ ] `study_material.promoted@1` records transcript/audio/pipeline/model
  lineage, conformance, uncertainty counts, and review state.
- [ ] Transcript/audio remain canonical lineage blobs but unindexed.
- [ ] Malformed island grammar degrades structure honestly and cannot overwrite
  KB-owned figure data.
- [ ] `doctor` aggregates deterministic bounded findings by source/scope.
- [ ] A representative semester dry run is inspected before tuning defaults.

## Verification

- Golden profile/promotion/replay fixtures and malformed-island adversarial
  cases.
- Real-semester read-only conformance report.

## Out of scope

- Repairing documents with a model, transcript retrieval, or tutor behavior.
