# Worker Brief: architecture scan

## Assignment

Run one read-only `improve-codebase-architecture` cycle for the exact module
scope named by the assigned Bead. Produce the assigned HTML report in
`/private/tmp`; do not edit repository files.

## Read First

- `/Users/ebrahimabdelwahed/.codex/skills/improve-codebase-architecture/SKILL.md`
- `/Users/ebrahimabdelwahed/.codex/skills/improve-codebase-architecture/HTML-REPORT.md`
- `/Users/ebrahimabdelwahed/.codex/skills/codebase-design/SKILL.md`
- `CONTEXT.md`
- `CONTEXT-MAP.md`
- relevant ADRs and recent commits for the assigned module scope

## Scope

You may read the repository and write only the explicitly reserved HTML path in
`/private/tmp`.

Do not change repository files, create commits, reserve another worker's files,
delegate recursively, or propose work outside the assigned module scope.

## Requirements

- Use the exact module/interface/depth/seam/adapter/leverage/locality vocabulary.
- Apply the deletion test to every candidate.
- Do not re-litigate an ADR without concrete friction and an explicit warning.
- Produce a self-contained Tailwind/Mermaid HTML report with before/after
  diagrams, recommendation strength, and one top recommendation.
- Report evidence, not generic refactoring advice.
- Send the absolute report path and concise findings through the Bead's Agent
  Mail thread. Do not close the Bead.

## Verification

- Confirm the HTML exists at the reserved path and is non-empty.
- Confirm no repository file changed and `git diff --check` passes.

## Report Back

Return the report path, candidate titles, top recommendation, ADR conflicts, and
whether any candidate is strong enough to grill next.
