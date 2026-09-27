# Plan: bounded lexical relevance fallback

Date: 2026-08-02 22:00 CEST
Area: Study Agent Harness lexical retrieval

## Goal

Allow concise, agent-generated natural-language queries to retrieve relevant
canonical chunks without requiring every term to occur in one chunk, while
preserving literal FTS safety, deterministic ranking, metadata filters, and
fail-closed insufficient-evidence behavior.

## Scope

- In scope: v0.1 SQLite FTS retrieval behavior, exact-title recovery, bounded
  relevance fallback, versioning, and retrieval regressions.
- Out of scope: Cardine's product prompt, classifiers, vector retrieval, new
  dependencies, or changes to citation validation.

## Approach

1. Preserve the precise literal-AND match as the highest-precision first pass.
2. Recover an exact canonical title match before broadening lexical matching.
3. For at most six safely tokenized query terms, search each literal term and
   retain only chunks matching a minimum term-coverage threshold.
4. Rank deterministically by coverage, lexical score, and canonical chunk id.
5. Keep longer/adversarial query strings fail-closed instead of broadening them.

## Risks

- A permissive fallback could turn weak matches into sufficient evidence.
- Search behavior changes require a strategy-version bump.
- Cardine and Harness are independent copies and require separate commits.

## Verification

- Contract and eval retrieval fixtures, including injection-shaped input.
- Full focused adapter suite, Ruff, mypy, and `git diff --check`.
