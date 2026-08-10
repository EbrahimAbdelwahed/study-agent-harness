# Task Bead: GAP-03 unsupported source-format tracer

Status: Done — host-trusted source-format tracer verified 2026-07-24
Priority: P1
Type: tracer-bullet
Depends On: GAP-02, TUT-06

## Outcome

The reference tutor handles an unsupported material extension honestly, offers
one safe manual fallback, records one deduplicated local gap, and continues the
conversation without claiming ingestion.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- First real learner journey from typed limitation to local report.

## Grilling Evidence

- Session/artifact: accepted feature spec plus existing
  `unsupported_extension` ingestion behavior.
- Decision state: scope approved 2026-07-18; implementation dependencies remain.
- ADR/glossary changes: none expected.

## Worker Profile

reuse `implementer`; independent `test-engineer`

Rationale: bounded host integration and scripted behavior eval.

## What To Do

- Map trusted `unsupported_extension` evidence to a source-format observation.
- Tell the learner the file was not ingested and request a supported `.txt` or
  `.md` derivative as the first manual workaround.
- Record suggested/succeeded/failed outcome without copying filename, path, or
  content; repeated attempts converge. Suggested is descriptive; succeeded or
  failed is accepted only from the GAP-02 trusted receipt binding.

## Acceptance Criteria

- [ ] A `.pdf`/other unsupported fixture never enters the source store and never
  appears as successfully processed.
- [ ] A supplied supported derivative retains its own provenance and limitation
  note; the original remains unmodified.
- [ ] Prompt injection in filename/content cannot alter the report or host policy.
- [ ] Main tutor context receives only the compact report receipt.
- [x] The scripted agent cannot forge a successful manual or tool workaround;
  the tracer requires an exact host-trusted limitation receipt in context.

## Verification

- Offline scripted tutor journey, duplicate/retry/injection/process-loss cases,
  architecture and full gates.

## Out Of Scope

- Native PDF/OCR/audio support or automatic conversion.
