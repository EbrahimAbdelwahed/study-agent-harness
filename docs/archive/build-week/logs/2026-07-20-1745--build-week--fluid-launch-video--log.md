# Log: Fluid Build Week launch video

Date: 2026-07-20 17:45 CEST
Area: build-week

## Summary

Replaced the 104-second synthetic-voice fallback with an 80-second, voice-over-ready launch film. The new edit follows one continuous tutor workspace through intake, source grounding, clarification, explanation, retrieval practice, memory update, and deterministic replay. No synthetic voice or paid generation is used.

## Files Changed

- `docs/build-week-proof/index.html`: continuous learner-to-runtime product story.
- `docs/build-week-proof/styles.css`: restrained product shell, causal motion, tutor interaction, and runtime proof.
- `docs/build-week-proof/app.js`: six cue-aligned chapters and deterministic capture entry points.
- `docs/build-week-narration-final.txt`: natural 80-second human voice-over script and delivery notes.
- `docs/build-week-captions-final.srt`: cue-aligned English captions.
- `docs/build-week-proof/README.md`: updated duration and QA routes.

## Verification

- Six final-state screenshots at 1280×720: reviewed; no collision, clipping, duplicate panel, or illegible runtime content found.
- Live browser capture: 800 frames over two continuous segments, each held to 100 ms frame cadence.
- `ffprobe study-agent-build-week-fluid-silent.mp4`: H.264, 1920×1080, 30 fps, exactly 80.0 seconds, no synthetic audio.
- Representative frames at 3, 10, 25, 41, 60, and 75 seconds: reviewed.
- `node --check docs/build-week-proof/app.js`: passed.
- `git diff --check`: passed.

## Output

- `/private/tmp/study-agent-build-week/final/study-agent-build-week-fluid-silent.mp4`
- `/private/tmp/study-agent-build-week/final/fluid-video-contact-sheet.png`

## Notes

- Record the human voice-over against the six fixed cue windows in `docs/build-week-narration-final.txt`.
- Upload `docs/build-week-captions-final.srt` separately after the voice-over mix.
