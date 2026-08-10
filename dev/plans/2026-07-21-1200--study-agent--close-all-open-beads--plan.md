# Plan: close all open study-agent beads

Date: 2026-07-21 12:00 CEST
Area: adaptive tutor / capability-gap / release

## Goal

Close every implementation-ready bead with essential, robust behavior and
honest evidence. Preserve explicitly deferred adapter decisions until a safe,
concrete selection is documented; then implement those adapters as separate
waves rather than weakening their contracts.

## Scope

- In scope: TUT-07A-D, TUT-08, GAP-01/02/03/04A/05A-C/06/07, followed by
  GAP-04B/05D/07B/08 when their adapter decisions can be resolved safely.
- Out of scope: `sbobby-web`, automatic external issues/goals/releases,
  unapproved paid/network effects, and rewriting completed harness owners.

## Wavefront

1. Parallel isolated branches: recall, product shell, local GAP MVP.
2. Integrate dependency checkpoints and run focused cross-lane tests.
3. Select and implement bounded optional adapters in fresh parallel lanes.
4. Run aggregated semantic/security review, full offline suite, Ruff, strict
   mypy, clean base/optional wheels, deterministic demos, and diff checks.
5. Reconcile status/checkboxes, archive completed specs where appropriate,
   update handoffs/index/Flywheel artifacts, and publish the integration branch.

## Invariants

- Per-course event stream remains canonical; operational GAP data never enters
  learner state.
- Skills/playbooks own study behavior; adapters translate technical protocols.
- Base install remains dependency-free and offline tests remain default.
- Seven StudyTools and existing fingerprints remain unchanged.
- User-owned Build Week working-tree changes are never overwritten or swept
  into implementation commits.

## Risks

- TUT-07 changes persistence/event/export contracts and optional FSRS packaging.
- GAP promotion must model authorization without invoking real external goals.
- TUT-08 may overlap user-authored submission docs; integration must preserve
  the user's version and resolve documentation manually.
- Deferred adapters require explicit dependency/auth/privacy choices; a bead is
  not `Done` merely because a scripted contract exists.

## Verification

- Focused bead tests and architecture gates per checkpoint.
- Full `pytest`, Ruff, strict mypy, `uv build`, clean-wheel matrices and demos.
- Aggregated reviewer/security findings applied before final status closure.
