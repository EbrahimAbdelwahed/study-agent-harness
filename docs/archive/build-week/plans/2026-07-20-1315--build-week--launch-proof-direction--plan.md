# Plan: Build Week launch proof of direction

Date: 2026-07-20 13:15
Area: Build Week demo

## Goal

Create a 30–40 second local visual proof that turns the real deterministic anatomy trace into a launch-quality story before any HeyGen render is attempted.

## Scope

- In scope: one self-contained web visualizer, four timed scenes, real checked-in demo data, desktop capture, and screenshot-based visual QA.
- Out of scope: product UI, new harness contracts, provider calls, HeyGen rendering, narration, and repository publication.

## Approach

1. Build an editorial 16:9 composition around one continuous event line.
2. Load only the verified `study-agent-demo --json` fields used on screen.
3. Provide autoplay, replay, deterministic scene URLs, and reduced-motion behavior.
4. Separate the tutor conversation from the replay proof, and expose the underlying CLI as a restrained final-scene inset.
5. Capture desktop, intermediate, mobile, and the four key scenes; fix visible defects.
6. Produce one 30–40 second local MP4 and stop for user review.

## Risks

- A static technical trace may still feel abstract; motion must reveal causality rather than decorate it.
- The proof must not imply a product UI or capabilities beyond the existing demo.

## Verification

- Compare displayed values with `.venv/bin/study-agent-demo --json`.
- Browser console clean; scene controls and reduced motion work.
- Screenshot QA at 1920×1080, 1024×768, and 390×844, including the dialogue and CLI states.
- Inspect representative frames and media metadata for the local MP4.
