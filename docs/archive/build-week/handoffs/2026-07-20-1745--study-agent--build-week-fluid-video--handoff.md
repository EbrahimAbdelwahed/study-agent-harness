# Handoff: Build Week fluid video

Date: 2026-07-20 17:45 CEST
Area: release / demo / submission

## Current State

An 80-second silent launch master and a cue-matched human voice-over script are complete. The Devpost project remains an unsubmitted draft and the old synthetic-voice fallback should no longer be uploaded.

## Completed

- Rebuilt the visual story as one continuous tutor interaction rather than a sequence of presentation panels.
- Added the adaptive lesson loop and subordinate runtime proof using values from the real offline trace.
- Captured and verified the silent 1920×1080 master.
- Rewrote the narration and captions for six exact cue windows.

## Remaining

- Record the human narration from `docs/build-week-narration-final.txt`.
- Mix that recording with `/private/tmp/study-agent-build-week/final/study-agent-build-week-fluid-silent.mp4` without changing its 80-second duration.
- Upload the mixed film to YouTube, add the public URL to Devpost, save the remaining custom form fields, and submit only after explicit approval.

## Important Context

- Final silent master: `/private/tmp/study-agent-build-week/final/study-agent-build-week-fluid-silent.mp4`.
- Do not use `/private/tmp/study-agent-build-week/final/study-agent-build-week-final.mp4`; its synthetic voice and panel timing were rejected.
- Devpost deadline remains 2026-07-22 00:00 UTC.

## Verification

- `ffprobe`: H.264, 1920×1080, 30 fps, 80.0 seconds, video-only.
- Representative-frame review: passed.
