---
phase: 04-filtering-and-deduplication
plan: "03"
subsystem: filtering
tags: [deduplication, sequencematcher, hashing, seen-store, pipeline-wiring]

# Dependency graph
requires:
  - phase: 04-01
    provides: normalize_title, compute_title_hash from hashing.py, Article schema with dedup fields
  - phase: 04-02
    provides: filter_by_relevance, filter_by_geo_tier functions
  - phase: 01-project-scaffold
    provides: SeenStore, SeenEntry schemas, save_seen loader utility
provides:
  - check_duplicate: two-stage dedup detection (exact hash + SequenceMatcher similarity)
  - filter_duplicates: complete dedup filter returning (filtered_articles, updated_seen)
  - add_to_seen: functional-style seen store update (no mutation)
  - main.py Phase 4 filter chain: relevance -> geo -> dedup wired sequentially
affects: [05-ai-analysis, 06-telegram-delivery]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Two-stage dedup: exact hash match first (O(n)), then SequenceMatcher ratio scan
    - UPDATE detection: 50-80% similarity range surfaces follow-up stories with original title reference
    - Functional filter returns: (list[Article], SeenStore) tuple, seen store updated inline per article
    - Pipeline wiring: filter chain reassigns `seen` variable at dedup stage before second save

key-files:
  created:
    - src/pipeline/filters/dedup_filter.py
    - tests/test_dedup_filter.py
  modified:
    - src/pipeline/main.py

key-decisions:
  - "best UPDATE candidate tracked during similarity scan — highest ratio in 50-80% range wins if multiple entries qualify"
  - "dedup_ref stores original human-readable title (not hash) — per research Pitfall 5, human-readable reference for delivery"
  - "seen variable reassigned by filter_duplicates in main.py — second save_seen after dedup captures both purge + new articles"
  - "SequenceMatcher called on normalized titles — punctuation and case differences ignored in similarity calculation"

patterns-established:
  - "Two-stage dedup pattern: O(n) hash scan short-circuit, then O(n) similarity scan with best-match tracking"
  - "Functional filter chain: seen store threaded through filter as return value, never mutated in-place"

requirements-completed: [AI-03, AI-04]

# Metrics
duration: 5min
completed: 2026-02-28
---

# Phase 4 Plan 03: Dedup Filter and Pipeline Wiring Summary

**Two-stage title deduplicator using SHA-256 hash lookup and SequenceMatcher similarity (50-80% UPDATE, >=80% DUPLICATE) with all Phase 4 filters wired sequentially into the pipeline entrypoint.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-28T09:01:20Z
- **Completed:** 2026-02-28T09:06:20Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Title-hash deduplicator with exact match (Stage 1) and SequenceMatcher similarity scan (Stage 2) — marks articles as NEW, UPDATE, or DUPLICATE
- UPDATE detection: 50-80% similarity returns UPDATE with original title as human-readable reference for delivery context
- filter_duplicates returns (filtered_articles, updated_seen) tuple — DUPLICATE articles excluded, NEW/UPDATE added to seen store
- Phase 4 three-stage filter chain wired into main.py: relevance -> geo -> dedup, with filter funnel logged at each stage
- 14 new dedup tests (120 total, zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Title-hash deduplicator with UPDATE detection** - `b46fda5` (feat)
2. **Task 2: Wire all Phase 4 filters into pipeline main.py** - `134b549` (feat)

_Note: TDD tasks — tests written first (RED), then implementation (GREEN), committed together after all tests pass._

## Files Created/Modified
- `src/pipeline/filters/dedup_filter.py` - check_duplicate, filter_duplicates, add_to_seen pure functions
- `tests/test_dedup_filter.py` - 14 tests: exact hash, punctuation normalization, similarity ranges, UPDATE detection, functional purity
- `src/pipeline/main.py` - Phase 4 filter chain wired (relevance -> geo -> dedup), second save_seen after dedup, filter funnel log

## Decisions Made
- Best UPDATE candidate tracked during similarity scan: if multiple seen entries fall in the 50-80% range, the one with highest ratio wins. Only one UPDATE ref is returned per article.
- `dedup_ref` stores the original human-readable title (not a hash) — ensures delivery phases can surface "UPDATE to: [original title]" without an additional lookup.
- The `seen` variable is reassigned by `filter_duplicates` in main.py. The first `save_seen` (after purge) and second `save_seen` (after dedup) are both intentional — first persists purge result, second persists new articles seen during this run.
- SequenceMatcher ratio computed on normalized titles (via `normalize_title`) so punctuation and case differences do not artificially inflate or deflate similarity scores.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Pre-commit ruff-format hook reformatted `test_dedup_filter.py` (split long function call arguments). Re-staged and committed cleanly on second attempt. No logic changes.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- Phase 4 filter pipeline complete: relevance scoring, geographic tier classification, and deduplication all wired and passing
- Phase 5 (AI Analysis) can consume `deduped_articles` directly — the list contains only NEW and UPDATE articles with dedup_status and dedup_ref set
- seen.json is updated each run with newly seen articles (title hash + url hash stored for next-run dedup lookups)
- Concern: Phase 5 prompt engineering for Indian real estate domain may need 2-3 calibration cycles before locking system prompt

---
*Phase: 04-filtering-and-deduplication*
*Completed: 2026-02-28*
