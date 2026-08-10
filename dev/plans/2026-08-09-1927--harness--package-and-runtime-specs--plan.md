# Plan: Harness package and future runtime specs

Date: 2026-08-09 19:27
Area: Study Agent Harness

## Goal

Materialize the approved Package Foundation and Future Runtime specifications
as independently verifiable slices that preserve the Harness context boundary.

## Scope

- In scope: `specs/package-foundation/`, `specs/future-runtime/`, contract and
  release dependency graphs, verification and transition-removal conditions.
- Out of scope: implementation code, Cardine product policy, publishing.

## Approach

1. Synthesize three independent drafts against CONTEXT and CONTEXT-MAP.
2. Materialize README handoffs and one file per seam-focused slice.
3. Audit one-owner architecture, graph acyclicity, placeholders, and commands.
4. Convert approved slices into implementation beads and worker briefs.

## Risks

- Exposing internal modules as stable API or retaining parallel lifecycle owners.
- Release gates depending on Cardine code rather than portable fixtures.

## Verification

- Structural spec audit, placeholder scan, link/path checks, and `git diff --check`.

