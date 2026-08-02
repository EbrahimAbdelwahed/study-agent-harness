# Log: Flywheel companion reframe

Date: 2026-07-21 11:25 CEST
Area: build-week

## Summary

Reframed the 39-second companion as a clearly distinct Codex workbench rather
than a second version of the Study Agent Harness UI. The revised companion
makes the human-approved Flywheel architecture explicit, fixes the process-DAG
arrow endpoints with SVG connections, enlarges presentation text, and includes
a clean terminal proof derived from the real deterministic `study-agent-demo`
output.

## Files Changed

- `docs/build-week-proof/flywheel-index.html`: replaced the faux application
  sidebar with the Codex workbench, Flywheel architecture, SVG DAG, and CLI
  proof scene.
- `docs/build-week-proof/flywheel-styles.css`: new presentation system,
  corrected diagram geometry, larger type, and compact terminal layout.
- `docs/build-week-proof/flywheel-app.js`: binds runtime-proof fields.
- `docs/build-week-proof/flywheel-data.json`: checked CLI command and output
  subset used by the proof scene.
- `docs/build-week-flywheel-narration.txt` and
  `docs/build-week-flywheel-captions.srt`: revised 39-second Codex/Flywheel
  narrative.
- `docs/build-week-proof/README.md`: updated companion description.

## Verification

- `node --check docs/build-week-proof/flywheel-app.js`: passed.
- `jq empty docs/build-week-proof/flywheel-data.json`: passed.
- Browser QA at 16:9: architecture, bead-DAG, terminal proof, gates, and
  handoff scenes reviewed; no clipping; SVG arrows terminate at node edges.
- `ffprobe study-agent-build-week-flywheel-companion-silent-v4.mp4`: H.264,
  1920×1080, 30 fps, 39.0 seconds, video-only.
- `ffprobe study-agent-build-week-submission-combined-silent-v4.mp4`: H.264,
  1920×1080, 30 fps, 119.0 seconds, video-only.
- `git diff --check`: passed.

## Outputs

- `/private/tmp/study-agent-build-week/final/study-agent-build-week-flywheel-companion-silent-v4.mp4`
- `/private/tmp/study-agent-build-week/final/study-agent-build-week-submission-combined-silent-v4.mp4`

## Notes

- The terminal presents a legible subset of the output in
  `src/study_agent/demo/anatomy.py`; it does not invent a runtime transcript.
- The companion remains silent and is timed for the revised human voice-over.
