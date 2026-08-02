# Plan: Fluid Build Week launch video

Date: 2026-07-20 17:00 CEST
Area: build-week

## Goal

Replace the panel-like 104-second fallback with a tightly timed, visually continuous launch video whose product interaction and technical proof remain synchronized. Deliver a voice-over-ready master and a natural spoken script.

## Scope

- In scope: rewrite the English narration, revise the local launch proof into a continuous tutor interaction, integrate runtime evidence without interrupting the product story, capture a deterministic silent master, and verify timing and representative frames.
- Out of scope: new harness behavior, fabricated product capabilities, paid generation, Devpost submission, and synthetic voice-over.

## Approach

1. Reframe the story around one learner request and one evolving workspace instead of separate presentation panels.
2. Use five short chapters with continuous spatial anchors: request, source grounding, tutor clarification, adaptive lesson, deterministic replay.
3. Keep the runtime as a small contextual inset and reveal technical evidence only when the visible interaction causes it.
4. Capture a 75–85 second silent master with fixed timing and provide cue-aligned narration for a human voice-over.
5. Inspect representative frames and media metadata; reject any version with dead holds, clipped content, or timing drift.

## Risks

- A product-like presentation must not imply unimplemented network or learner-facing contracts.
- Dense runtime evidence can compete with the learner story; it must remain subordinate.
- Browser capture must use the same deterministic trace data as the offline demo.

## Verification

- Compare displayed data with `docs/build-week-proof/demo-data.json` and the existing reference trace.
- Capture representative frames across all chapters and inspect them at 1920×1080.
- Use `ffprobe` to verify exact duration, resolution, frame rate, and absence of synthetic audio.
- Run `git diff --check`.
