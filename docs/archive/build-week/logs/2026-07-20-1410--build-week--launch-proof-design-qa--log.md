# Log: Build Week launch proof design QA

Date: 2026-07-20 14:10
Area: build-week

## Summary

Completed and revised a local visual proof for the Build Week demo direction. The proof uses a single event spine across four editorial scenes and displays only values projected from the real reference demo: learner context, source identity and checksum, evidence, clarification, selected focus, replay traces, gateway runtime events, and parity.

No HeyGen render was requested and no external video credit was consumed.

## Design Direction

- Thesis: a study agent should remember the learner and prove what it did.
- Visual system: restrained graphite, warm white, data blue, and anatomical red; large typography; sparse composition; one idea per scene.
- Narrative: learner encounter -> grounded source -> adaptive tutor dialogue -> deterministic replay.
- Explicitly avoided dashboard grids, fake metrics, terminal footage, and decorative product chrome.

## Files Changed

- `docs/build-week-proof/index.html`: accessible three-scene narrative structure.
- `docs/build-week-proof/styles.css`: responsive editorial layout and motion system.
- `docs/build-week-proof/app.js`: data loading, deterministic scene states, autoplay, and replay.
- `docs/build-week-proof/demo-data.json`: checked projection of the real harness reference demo.
- `docs/build-week-proof/README.md`: local preview and QA instructions.
- `dev/plans/2026-07-20-1315--build-week--launch-proof-direction--plan.md`: bounded proof plan.

## Verification

- `PYTHONPATH=src .venv/bin/python -c '...'`: demo projection matches `run_reference_demo()`.
- Browser visual QA at 1920x1080, 1024x768, and 390x844: passed.
- All four deterministic scene URLs loaded their bound demo data during browser capture without a visible failure state.
- 1024px collision found during QA: fixed by tightening the second scene and suppressing the redundant second evidence quotation at that breakpoint.
- User review found that the prior clarification and replay frames shared too much composition. The clarification is now a spatial tutor-student exchange; replay is a horizontal state trace with a subordinate runtime CLI inset.
- The CLI displays the real `gateway_trace` projection and parity rather than authored terminal output.
- `ffprobe`: H.264, 1920x1080, 10 fps, 34.5 seconds, 560800 bytes.
- `git diff --check`: passed.

## Output

- `/private/tmp/study-agent-build-week/final/study-agent-launch-proof-v2.mp4`

## Limitations

- This is a silent direction proof, not the final submission edit.
- Narration, sound design, HeyGen presenter footage, and final submission assembly remain intentionally out of scope until the direction is approved.
