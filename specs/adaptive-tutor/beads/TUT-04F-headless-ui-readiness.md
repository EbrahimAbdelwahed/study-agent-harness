# Task Bead: TUT-04F headless artifact-flow and UI readiness

Status: Done
Priority: P0
Type: contract
Depends On: TUT-04C3, TUT-04D, TUT-04E1, TUT-04E2

## Worker Profile

Reuse `grounded-study-artifact-worker`; use `reviewer` and `test-engineer` for
the final cross-owner story rather than adding UI code.

## Outcome

A credential-free scripted host can exercise the complete material-to-proposal-
to-decision path headlessly, proving the harness contracts needed by a minimal
conversation-first UI.

## Acceptance Criteria

- [x] One scripted lesson flow ingests trusted text/Markdown, creates a lesson
  plan, runs isolated profile workers, exposes a compact tutor summary plus typed
  detailed review view, commits selected verified pages, records human accept or
  reject decisions plus a separate human-authored revision, and replays
  byte-identically after process loss.
- [x] One scripted exam flow ingests trusted exam samples, runs isolated grounded
  analysis, exposes observed formats/topics/limitations with citations, commits
  the verified blueprint proposal, and records a human decision.
- [x] The main tutor trace contains no raw lesson/exam body, worker scratch
  output, credentials, principal identifiers, provider-private response IDs, or
  unbounded candidate payload. Pre-commit detail uses verified opaque evidence
  handles; committed provenance and export retain the resolvable source linkage.
- [x] Recomputing the pure lesson planner over the same host-declared structure
  produces identical canonical bytes. Worker fan-out, dialogue, artifact commit,
  and decision operations resume idempotently at their durable boundaries
  without duplicate model calls or events.
- [x] A provider-neutral scripted model is the default fixture. One opt-in generic
  model-adapter smoke may run separately; no DeepSeek/OpenAI/SDK dependency enters
  core contracts.
- [x] The story produces a deterministic eval report covering coverage,
  omissions, grounding failures, proposed/accepted/rejected counts, hierarchy
  roles, and provenance. It does not label these metrics mastery.
- [x] Exact seven StudyTools, old repository replay, public capability contracts,
  and no-`sbobby-web` scope remain green.

## Likely Files / Packages

- scripted integration/eval fixtures under `tests/integration/` and `tests/evals/`
- no web/UI package
- no new production owner, capability, StudyTool, or headless orchestration API

## Out of Scope

- Browser UI, auth, billing, subscription equivalence, scheduling, mastery,
  hosted queues, PDF/OCR/audio, live Anki, GEPA optimization, and `sbobby-web`.

## Verification

- Full lesson and exam scripted stories, process-loss checkpoints at every
  boundary, secret scan, deterministic replay/report, Ruff, strict mypy, wheel,
  Python 3.12/3.13, architecture/tool parity, and full offline suite.

## Grilling Evidence

This bead owns the pre-UI proof requested after C1/C2/C3/D/E: the minimal UI may
begin only after the same flows work through typed headless contracts without
privileged shortcuts.

## Plan Review

The cross-owner story reuses the existing ingestion, pure planner, isolated
worker, verified generated-owner, artifact lifecycle, replay, and export owners.
Adding a production "headless UI" orchestrator was rejected because it would
duplicate those owners. Source linkage is asserted from verified commit
provenance and export; the authorized pre-commit review view intentionally keeps
only opaque evidence handles.
