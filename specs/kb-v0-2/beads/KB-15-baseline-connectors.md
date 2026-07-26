# KB-15: Baseline connectors and study-material profile

Status: Proposed parent — child beads own implementation
Risk: Medium
Depends On: KB-06, KB-07, KB-14
Parent coverage: §6, Appendix A; M4

## Outcome

Markdown documents, externally converted PDFs, derived study material, exam
banks, and plain notes enter through conforming profiles and produce real
conformance evidence without branching the domain model.

## Child beads

- [KB-15A](KB-15A-markdown-notes-connectors.md): Markdown and plain-notes
  profiles over the offline substrate/tree/unitizer.
- [KB-15B](KB-15B-pdf-connector-profile.md): externally converted PDF
  substrate and page-map profile.
- [KB-15C](KB-15C-study-material-profile-doctor.md): Appendix A study-material
  dialect, promotion/lineage, `doctor`, and real-semester conformance.

The `exam_bank` connector lands with KB-19 after its item contract exists; it
must not predeclare a second exam-item shape here.

## Out of scope

- PDF conversion, transcription, OCR, model repair, or profile-specific ranking.
