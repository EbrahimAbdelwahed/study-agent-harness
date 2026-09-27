# Automatic review fixes for PR #58

The adaptive tutor branch includes main at 11c21b1 through merge 3599bbc.
This change addresses the three Codex GitHub review findings on that merge.

- Literal FTS lookup now uses all safely quoted tokens before any stop-word filtering.
  Technical terms such as source, developer, table, column and value remain searchable.
  Instruction-shaped text remains inert searchable source text; retrieval cannot grant authority.
- Bounded relevance fallback runs only for at most six informative terms. Longer
  queries can still match literally but cannot promote evidence from only two terms.
- Both public search/question schemas declare the existing 512-character retrieval
  limit. Grounding validates the same limit before creating a run or emitting events.
  The two intentional manifest fingerprint changes are reflected in all discovery snapshots.

Nine new regression cases failed before the fixes. Full offline pytest now reports
2176 passed and 4 skipped. Ruff passes; mypy passes on all 474 source files.
The model smoke tests remain opt-in. Distribution tests are exercised by CI after
building its wheel and source archive. No local semantic reviewer was launched.

Existing local README, .gitignore, Build Week artifacts and duplicate files were
preserved outside this scoped commit. CI and automatic review must assess the new
submitted head before merge; earlier green results do not establish that outcome.
