# Plan: Flywheel companion reframe

Date: 2026-07-21 10:15 CEST
Area: build-week

## Goal

Reframe the companion portion of the Build Week video as a clearly distinct
Codex and adapted-Flywheel process presentation, while keeping the combined
submission master at 1:59.

## Scope

- In scope: remove the faux product sidebar; enlarge presentation text; replace
  inaccurate CSS connector lines with explicit SVG arrows; make the Codex
  workflow and human approval boundary explicit; add a compact, legible terminal
  proof derived from the real offline CLI demo; update companion narration,
  captions, capture, and media verification.
- Out of scope: changing harness behavior, presenting the demonstrative UI as a
  shipped product interface, inventing runtime output, or changing the main
  80-second tutor film.

## Approach

1. Make the companion a different visual object: a Codex workbench with a
   centered process canvas rather than the study harness dashboard shell.
2. Render the Flywheel architecture as a pseudo-static, SVG-connected causal
   path: approved spec → bead DAG → bounded worker → tests/reviews → durable
   handoff. Keep human approval outside the agent node.
3. Show the actual `study-agent-demo` invocation followed by a stripped, exact
   subset of its deterministic output in a terminal proof box.
4. Preserve the six-scene, 39-second timing contract, then re-capture and
   concatenate it after the unchanged 80-second main master.

## Risks

- The process view can overstate Codex autonomy; human approval and verified
  artifacts must remain visible.
- The terminal can become unreadable; restrict it to the command and four
  high-signal output lines from the real demo.

## Verification

- `node --check docs/build-week-proof/flywheel-app.js`
- `jq empty docs/build-week-proof/flywheel-data.json`
- Visual QA of every fixed scene at 16:9, including SVG arrow endpoints and the
  terminal proof scene.
- `ffprobe` of the regenerated companion and final combined master.
- `git diff --check`
