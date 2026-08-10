# Log: TUT-08 browser reference close

Date: 2026-07-24 18:00
Area: adaptive-tutor / product shell

## Summary

Added the smallest browser-visible TUT-08 reference surface without a web
framework. A localhost-only standard-library server serves a packaged,
accessible HTML page and deterministic JSON routes. The page accepts bounded
free-form entry and renders conversation, material, evidence, conflict, and
safe optional due-review states by projecting the existing offline shell
journey; it does not own canonical tutor state.

## Files Changed

- `src/study_agent/demo/browser.py`: localhost server, stable JSON projection,
  bounded entry handling, and CLI entry point.
- `src/study_agent/demo/browser.html`: dependency-free accessible reference
  page and state renderer.
- `src/study_agent/demo/product_shell.py`: expose the existing anatomy
  context-state projection to browser consumers.
- `tests/unit/demo/test_browser.py`: projection, bounds, static page, and
  deterministic JSON checks.
- `tests/integration/demo/TUT08/test_browser_surface.py`: real local HTTP
  journey check.
- `pyproject.toml`: browser entry point and package data.
- `docs/product-shell.md`: browser command, route contract, and provider
  boundary documentation.
- `specs/adaptive-tutor/beads/TUT-08-build-week-product-shell.md`: acceptance
  status and remaining release gates.
- `specs/adaptive-tutor/assets/tut08-browser-final.jpg`: post-submit desktop
  browser evidence after the visual correction.

## Verification

- `python3 -m compileall -q src/study_agent/demo tests/unit/demo tests/integration/demo/TUT08`: passed.
- `PYTHONPATH=src python3` pure `BrowserSurface` smoke: passed; offline
  recovered status, context sequence, and three-step trace were returned.
- Escalated loopback smoke using `create_server("127.0.0.1", 0)`: passed;
  `GET /` returned 200 packaged HTML and `GET /api/state` returned stable
  JSON with recovered status, three trace entries, material checksum, and
  evidence sequence 2.
- `/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/study-agent-harness/.venv/bin/python -m pytest tests/unit/demo tests/integration/demo/TUT08 -q`: 13 passed.
- `/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/study-agent-harness/.venv/bin/python -m mypy src/study_agent/demo`: passed.
- `ruff check src/study_agent/demo tests/unit/demo tests/integration/demo/TUT08`: passed.
- `pytest tests/architecture/test_import_boundaries.py tests/architecture/test_tutor_host_boundaries.py -q`: 8 passed.
- Escalated `uv build`: passed; wheel included `browser.html` and the
  `study-agent-shell-web` entry point. Generated `dist/` and egg-info files
  were removed after the smoke.
- In-app browser `POST /api/entry` smoke: passed with a bounded free-form
  learner entry and recovered deterministic host trace.
- Independent screenshot critique: found a high-confidence SHA-256 overflow;
  `overflow-wrap: anywhere` was applied to metadata and pinned by a static-page
  regression assertion.
- Desktop post-fix DOM geometry: no right-edge overflow; the only negative
  position is the intentional off-screen skip link before focus.
- Mobile 390 px DOM geometry: `scrollWidth == clientWidth == 390`; panels
  collapse to one column. The in-app browser had a non-default visual zoom, so
  geometry rather than that zoomed screenshot is the responsive evidence.
- `ruff format --check` reports one pre-existing formatting difference in
  `src/study_agent/demo/anatomy.py`; no unrelated file was reformatted.

## Remaining

- TUT-08 is not marked Done: the configured GPT host journey and final Build
  Week submission artifacts are still missing.
- The browser server deliberately has no implicit GPT-5.6 mode. A configured
  provider may be composed by an embedding host through the existing public
  host port; no credentials are accepted or exposed by this local reference
  server.
