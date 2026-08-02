# Log: Chunked Build Week voiceover montage

Date: 2026-07-22 00:37 CEST
Area: build-week launch video

## Summary

Verified and imported the eight manually downloaded ElevenLabs Jerry B MP3s, mapped them to blocks 1–8 by their embedded generation timestamps, and built the 3:55 montage defined by `docs/build-week-montage-sheet.md`. Each narration block remains at its generated speed. The silent 138-second source was retimed chapter by chapter to the target windows, while the existing one-second black transition between blocks 5 and 6 remains one second.

The mixed narration starts at 0.0, 11.0, 22.0, 38.4, 69.8, 127.7, 153.8, and 211.7 seconds. The final audio was normalized and encoded as mono AAC at 48 kHz.

## Files Changed

- `output/voiceover-chunks-v2/block_01.mp3` through `block_08.mp3`: verified, ordered copies of the downloaded ElevenLabs generations.
- `output/Study Agent Harness - Launch Video with Chunked Voiceover.mp4`: final 4K, 3:55 chapter-retimed montage.
- `output/Study Agent Harness - Chunked Voiceover Contact Sheet.png`: representative midpoint frame from each of the eight chapters.
- `dev/logs/2026-07-22-0037--build-week--chunked-voiceover-montage--log.md`: montage and verification record.

## Verification

- `ffprobe` on the eight source MP3s: 10.710, 10.684, 14.158, 24.085, 49.763, 24.503, 49.998, and 20.506 seconds; MP3, mono, 44.1 kHz.
- `ffprobe -count_frames` on the final: exactly 235.000 seconds and 7,050 frames; 3840x2160 H.264 at 30 fps; mono AAC at 48 kHz; 10,781,278 bytes.
- `silencedetect=noise=-40dB:d=0.2`: major inter-block air ends at 11.037, 22.105, 38.477, 69.924, 127.819, 153.909, and 211.794 seconds, confirming the intended starts after MP3/AAC encoder padding.
- `ebur128=peak=true`: -16.7 LUFS integrated loudness, 4.0 LU loudness range, and -1.4 dBFS true peak.
- Contact-sheet inspection: all eight chapter midpoint frames are legible and match their expected visual chapter.

## Notes

- The previous 2:18 voiceover montage and slow backup were preserved unchanged.
- Blocks 5 and 7 require the largest chapter retiming, as already documented in the montage sheet.
