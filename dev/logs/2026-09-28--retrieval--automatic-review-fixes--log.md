# Automatic review fixes for PR #58

The adaptive tutor branch includes main at 11c21b1 through merge 3599bbc.
The fixes address five Codex GitHub review findings across two submitted heads.

- Literal FTS lookup uses all safely quoted tokens before stop-word filtering.
  Technical terms such as source, developer, table, column and value remain searchable.
  Instruction-shaped text stays inert searchable data and cannot grant authority.
- Relevance fallback is limited to at most six informative terms. Longer questions
  may match literally but cannot promote evidence from only two terms.
- Term coverage is aggregated in SQL before the final result limit. A relevant
  intersection after 64 single-term chunks is retained; all scope, revision,
  trust and role filters still apply to the final candidate set.
- The exact seven public v1 manifests and fingerprints remain byte-stable.
  Remove the new downstream 512-character cap rather than narrow the existing
  unbounded public schemas. Longer grounding requests complete normally and
  repeated requests keep their canonical idempotency guarantees.

Both rounds included red-before-fix regressions. The final offline suite reports
2177 passed and 4 skipped. Ruff passes; mypy passes on all 474 source files.
Model smoke tests remain opt-in; CI builds and verifies the distribution artifacts.
No local semantic reviewer was launched.

Existing local README, .gitignore, Build Week artifacts and duplicate files are
preserved outside these scoped commits. Current-head CI and automatic review are
required before merge; earlier green results do not establish that outcome.
