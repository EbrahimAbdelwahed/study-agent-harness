# Log: Build Week voiceover mix

Date: 2026-07-21 23:21
Area: build-week launch video

## Summary

Downloaded the approved ElevenLabs Jerry B take, separated it at the seven paragraph boundaries, and aligned the eight narration blocks to the 2:18 launch-video cue windows. An initial time-stretched mix was rejected because parts of the delivery sounded unnaturally slow. The delivered revision preserves ElevenLabs' original speaking speed and uses the remaining cue time as pauses. The final mix is normalized to -16 LUFS and encoded as mono AAC at 48 kHz.

## Files Changed

- `output/Study Agent Harness - Voiceover Jerry B.mp3`: preserved original ElevenLabs take.
- `output/Study Agent Harness - Launch Video with Voiceover.mp4`: final 4K launch video with synchronized, natural-speed voiceover.
- `output/Study Agent Harness - Launch Video with Voiceover - Slow Backup.mp4`: retained rejected time-stretched version for comparison.

## Verification

- `ffprobe -v error -show_entries format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels -of json <final>`: 138.000 seconds, 3840x2160 H.264 at 30 fps, mono AAC at 48 kHz.
- `ffmpeg -v error -i <source/final> -map 0:v:0 -c copy -f md5 -`: both video streams returned `70e2a023a517e74a0e9f208dfcfe3479`; no video re-encoding or visual change.
- `ffmpeg -i <final> -map 0:a:0 -af silencedetect=noise=-40dB:d=1.0 -f null -`: confirmed natural-speed blocks separated by 2.5–10.4 second cue pauses and 4.7 seconds of closing silence.

## Notes

- Source take duration is 95.791 seconds; the delivered revision applies no tempo adjustment.
