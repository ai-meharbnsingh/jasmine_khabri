---
phase: 04-filtering-and-deduplication
plan: "01"
subsystem: filtering
tags: [pydantic, keyword-matching, text-normalization, hashing, sha256, relevance-scoring, tdd]

# Dependency graph
requires:
  - phase: 03-news-fetching
    provides: Article schema and fetched articles from RSS/GNews
  - phase: 01-project-scaffold
    provides: KeywordsConfig schema with active_keywords() and exclusions

provides:
  - normalize_title() and compute_title_hash() canonical text utilities (src/pipeline/utils/hashing.py)
  - score_article() — exclusion short-circuit + keyword accumulation (title=20, body=10)
  - filter_by_relevance() — applies threshold and exclusion gates, returns model_copy with relevance_score
  - Article schema extended with relevance_score, geo_tier, dedup_status, dedup_ref (all optional, backward-compatible)
  - filters/ subpackage initialized

affects:
  - 04-02 (URL deduplication — imports normalize_title and hashing utilities)
  - 04-03 (geographic filtering — reads geo_tier field set by next filter stage)
  - 05-ai-analysis (receives pre-filtered articles, never sees zero-score or excluded articles)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Exclusion short-circuit before scoring — cheapest rejection first"
    - "model_copy(update={...}) for immutable Article mutation — original never modified"
    - "Pure function filter design — no side effects, easily testable"
    - "Canonical normalization in shared hashing.py — all phases import from one source"
    - "TDD RED/GREEN cycle with separate stub and implementation commits"

key-files:
  created:
    - src/pipeline/utils/hashing.py
    - src/pipeline/filters/__init__.py
    - src/pipeline/filters/relevance_filter.py
    - tests/test_relevance_filter.py
  modified:
    - src/pipeline/schemas/article_schema.py

key-decisions:
  - "Exclusion check runs before keyword scoring — short-circuits at O(n_exclusions) instead of O(n_keywords)"
  - "normalize_title uses NFD decomposition so 'Phase-4' and 'Phase 4' produce identical tokens"
  - "score_article returns (bool, int) tuple — caller decides rejection vs logging; no side effects"
  - "All four Phase 4 filter fields on Article use Python defaults — zero code changes needed in Phase 3 constructors"
  - "hashing.py is the canonical normalization source — 04-02 dedup MUST import from here, not reinvent"

patterns-established:
  - "Filter function signature: (articles: list[Article], keywords: KeywordsConfig, threshold: int) -> list[Article]"
  - "Score function signature: (article: Article, keywords: KeywordsConfig) -> tuple[bool, int]"
  - "Relevance threshold default = 40 — one title keyword (20) plus one body keyword (10) is not enough; need 2 title hits"

requirements-completed: [FETCH-03, FETCH-04]

# Metrics
duration: 13min
completed: 2026-02-28
---

# Phase 4 Plan 01: Relevance Filter Summary

**Keyword relevance scorer with exclusion short-circuit: pure functions score_article()/filter_by_relevance() using KeywordsConfig, with Article schema extended for Phase 4 filter fields and shared NFD hashing utilities**

## Performance

- **Duration:** 13 min
- **Started:** 2026-02-28T08:29:21Z
- **Completed:** 2026-02-28T08:43:09Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 5

## Accomplishments

- Article schema extended with four optional Phase 4 fields (relevance_score, geo_tier, dedup_status, dedup_ref) — zero regressions in 73 existing tests
- Shared hashing utilities (normalize_title, compute_title_hash) established as canonical normalization source for all Phase 4 modules
- Relevance filter with exclusion short-circuit eliminates noisy articles before they reach the AI analysis pipeline (Phase 5)
- 13 new TDD tests covering scoring logic, exclusion behavior, threshold filtering, immutability, and edge cases
- Full test suite: 86 tests passing, ruff clean

## Task Commits

Each task was committed atomically:

1. **Task 1: RED phase — stubs + failing tests** - `6818822` (test)
2. **Task 2: GREEN phase — full implementation** - `c2b7317` (feat)

_Note: TDD tasks have two commits (test RED → feat GREEN)_

## Files Created/Modified

- `src/pipeline/schemas/article_schema.py` — Extended with relevance_score, geo_tier, dedup_status, dedup_ref (all optional with defaults)
- `src/pipeline/utils/hashing.py` — normalize_title() and compute_title_hash() canonical utilities
- `src/pipeline/filters/__init__.py` — filters subpackage init
- `src/pipeline/filters/relevance_filter.py` — score_article() and filter_by_relevance() pure functions
- `tests/test_relevance_filter.py` — 13 tests: TestScoreArticle, TestExclusionFilter, TestFilterByRelevance

## Decisions Made

- Exclusion check runs before keyword scoring — short-circuits at O(n_exclusions) instead of O(n_keywords). Since exclusions are small (5 items) vs keywords (67+ active), this is a minor perf gain but enforces intent: "obituary" always wins regardless of score.
- normalize_title uses NFD decomposition so "Phase-4" and "Phase 4" produce identical tokens. Hyphens become spaces after `[^a-z0-9\s]` stripping.
- score_article returns (bool, int) tuple — separation of concerns: caller logs or routes differently for excluded vs low-score.
- All four Phase 4 filter fields on Article use Python defaults — Article() constructors in Phase 3 tests/code need zero changes.
- hashing.py is the canonical normalization source — Phase 04-02 dedup MUST import normalize_title from here, not reinvent it.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Ruff pre-commit hook reformatted files on first commit attempt (unused imports removed from stubs, line length formatting). Re-staged and committed successfully on second attempt. No logic changes.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Relevance filter complete and tested — Phase 04-02 (URL deduplication using seen.json) can import from `pipeline.filters.relevance_filter`
- hashing.py canonical normalization ready for dedup title matching
- Article schema extended with all Phase 4 fields — 04-02 and 04-03 can set geo_tier and dedup_status without further schema changes
- 86 tests passing, no regressions

## Self-Check: PASSED

All created files verified on disk. Both task commits verified in git log.

- FOUND: src/pipeline/utils/hashing.py
- FOUND: src/pipeline/filters/__init__.py
- FOUND: src/pipeline/filters/relevance_filter.py
- FOUND: tests/test_relevance_filter.py
- FOUND: .planning/phases/04-filtering-and-deduplication/04-01-SUMMARY.md
- COMMIT 6818822: test(04-01): add failing tests for relevance filter (RED)
- COMMIT c2b7317: feat(04-01): implement relevance filter and hashing utilities (GREEN)

---
*Phase: 04-filtering-and-deduplication*
*Completed: 2026-02-28*
