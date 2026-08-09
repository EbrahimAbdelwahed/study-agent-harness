# Handoff: Build Week video and submission draft

Date: 2026-07-20 15:18 CEST
Area: release / demo / submission

## Current State

The Devpost project remains an unsubmitted `submission_draft`. Its title,
tagline, long description, technologies, public repository link, and launch-proof
thumbnail are saved. A final local 1:44 submission video with English narration
and an embedded selectable English subtitle track is ready.

## Completed

- Uploaded the approved launch proof and six real project clips as HeyGen assets.
- Attempted one continuation and one clean HeyGen generation; both failed without
  a failure code or usable output. No further paid attempt was made.
- Produced a deterministic local fallback from the seven real assets, local
  English speech synthesis, and authored captions.
- Saved Devpost project version 3 and uploaded the tutor-dialogue thumbnail.
- Recorded the core `/feedback` Session ID as
  `019f6015-44e7-7b01-973f-b3a75df6577e`.

## Remaining

- Sign in to YouTube Studio and upload
  `/private/tmp/study-agent-build-week/final/study-agent-build-week-final.mp4`
  as a public video.
- Add the public YouTube URL to Devpost.
- Sign in to Devpost in the in-app browser and save the custom submission answers:
  Individual; Italy; Education; public repository URL; offline judge instructions;
  Session ID; developer-tool installation instructions.
- Review the complete draft and submit only after explicit user approval.

## Important Context

- Do not retry HeyGen automatically. Session `60103cb906a9495a97b3f2b2adabc0a4`
  and video `10baa9bb6d0e4ba49414e68a9a7e56d7` failed without an error message.
- The local final is 1920x1080 H.264, AAC mono audio, 104.2 seconds, and includes
  an English `mov_text` subtitle stream.
- Devpost deadline is 2026-07-22 00:00 UTC.
- Do not submit the Devpost entry without explicit approval.

## Verification

- `ffprobe ... study-agent-build-week-final.mp4`: H.264 1920x1080, AAC audio,
  English subtitle track, duration 104.2 seconds.
- Representative-frame visual review: passed after rejecting oversized burned-in
  captions in favor of a selectable subtitle track.
- `git diff --check`: passed.
