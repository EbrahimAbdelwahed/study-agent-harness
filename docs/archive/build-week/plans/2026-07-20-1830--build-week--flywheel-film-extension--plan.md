# Plan: Build Week Flywheel film extension

Date: 2026-07-20 18:30 CEST
Area: build-week

## Goal

Add an explicit demonstrative-UI disclaimer to the accepted 80-second tutor film and create a short, visually continuous companion presentation showing how Codex and the adapted agent Flywheel turned approved specifications into dependency-aware beads, bounded implementations, tests, reviews, and durable handoffs.

## Scope

- In scope: disclaimer in the accepted visualizer; one runtime architecture view; a separate 30–40 second Flywheel companion using the same visual system; one or two architecture/process views; cue-timed narration and captions; deterministic QA routes.
- Out of scope: changing harness behavior, claiming autonomous architectural authority, fabricating run artifacts, changing the accepted tutor story or replacing its visual language.

## Approach

1. Preserve the accepted tutor film and add the disclaimer early without competing with its hook.
2. Ground every Flywheel claim in existing `docs/flywheel-runs`, task beads, reviews, README, and handoffs.
3. Create a companion visualizer with the same stage, masthead, typography, color system, motion curves, timeline, and camera.
4. Show `approved spec → bead DAG → bounded worker → tests/reviews → durable handoff` as one causal trace, not a repository slideshow.
5. Provide a short human voice-over timing contract and final-state routes for visual QA.

## Risks

- The companion can imply the agent approved its own architecture; approval and authoritative state must remain explicitly human/workflow-owned.
- Generic architecture diagrams would break visual continuity.
- Additional content must remain optional so the accepted 80-second submission master is not destabilized.

## Verification

- Compare visible claims with selected Flywheel manifests, task files, and review reports.
- Run JavaScript syntax checks and `git diff --check`.
- Inspect every fixed scene at 16:9 and verify the disclaimer is readable.
- Verify the companion timing matches its narration cue windows.
