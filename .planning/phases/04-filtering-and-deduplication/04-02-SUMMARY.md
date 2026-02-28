---
phase: 04-filtering-and-deduplication
plan: "02"
subsystem: filtering

tags: [python, pydantic, geo-filter, city-taxonomy, tdd]

# Dependency graph
requires:
  - phase: 04-01
    provides: Article schema with relevance_score and geo_tier fields; hashing utilities

provides:
  - classify_geo_tier() pure function — assigns Tier 1/2/3 to articles based on city mentions
  - filter_by_geo_tier() pure function — applies tier-specific relevance_score thresholds
  - TIER_1_CITIES, TIER_2_CITIES, GOV_SOURCES frozensets for city taxonomy
  - National-scope government feed articles (MOHUA, NHAI, AAI, Smart Cities) classified as Tier 1
  - geo_tier field populated on all passing articles via model_copy (immutable pattern)

affects: [04-03, 05-ai-analysis-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Frozenset O(1) lookup for city taxonomy (TIER_1_CITIES, TIER_2_CITIES, GOV_SOURCES)
    - model_copy(update=...) for immutable Article field mutation
    - Tier-based gating with score thresholds (Tier 1 always, Tier 2 >= 60, Tier 3 >= 85)
    - TDD RED/GREEN pattern for filter functions (stub + failing tests first)

key-files:
  created:
    - src/pipeline/filters/geo_filter.py
    - tests/test_geo_filter.py
  modified: []

key-decisions:
  - "Tier 1 cities always pass regardless of relevance_score — ensures major metro stories always reach delivery"
  - "Government sources (MOHUA, NHAI, AAI, Smart Cities) with no city match treated as Tier 1 national-scope — per 04-RESEARCH.md Pitfall 4"
  - "Tier 2 threshold 60 and Tier 3 threshold 85 are Phase 4 proxies — Phase 5 AI classification will refine with semantic understanding"
  - "City scan runs on title+summary concatenated (lowercased) — catches city mentions in lead paragraph, not just headline"

patterns-established:
  - "frozenset for O(1) taxonomy lookup: same pattern as GOV_SOURCES/TIER_1_CITIES/TIER_2_CITIES — use for any categorical set in pipeline"
  - "Tier-based gating: caller provides articles with relevance_score already set (from 04-01) — geo filter is a second-stage pass-through"

requirements-completed: [FETCH-05]

# Metrics
duration: 8min
completed: 2026-02-28
---

# Phase 4 Plan 02: Geographic Tier Classifier Summary

**Geographic tier classifier with frozenset city taxonomy, government feed national-scope override, and tier-specific relevance_score thresholds (T1 always, T2>=60, T3>=85)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-28T08:46:00Z
- **Completed:** 2026-02-28T08:54:11Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2

## Accomplishments

- `classify_geo_tier()` classifies articles into Tier 1 (major metros), Tier 2 (secondary cities), or Tier 3 (everything else) by scanning title+summary using frozenset O(1) lookup
- Government feed sources (MOHUA, NHAI, AAI, Smart Cities) with no city match automatically classified as Tier 1 national-scope articles
- `filter_by_geo_tier()` applies tier-specific gating: Tier 1 always included, Tier 2 needs score >= 60, Tier 3 needs score >= 85; sets geo_tier on all passing articles
- 20 new tests, full suite now 106 tests passing with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Geographic tier classifier and filter (RED)** - `307bfb3` (test)
2. **Task 2: Implement geo filter to pass all tests (GREEN)** - `6149b5d` (feat)

_Note: TDD tasks have two commits — failing tests first, then implementation._

## Files Created/Modified

- `src/pipeline/filters/geo_filter.py` — Geographic tier classifier with TIER_1_CITIES/TIER_2_CITIES/GOV_SOURCES frozensets, classify_geo_tier() and filter_by_geo_tier() pure functions
- `tests/test_geo_filter.py` — 20 tests covering tier 1/2/3 classification, government feed national-scope logic, summary scanning, and tier-based score threshold filtering

## Decisions Made

- Government sources with no city match are Tier 1: national-scope announcements from MOHUA/NHAI/AAI/Smart Cities are always high-priority regardless of specific city mention — per 04-RESEARCH.md Pitfall 4 recommendation
- Tier 2 threshold 60 and Tier 3 threshold 85 are Phase 4 proxies for AI priority; noted in docstrings as Phase 5 refinement points
- City scan on concatenated title+summary (lowercased): catches city mentions in lead sentences, not just headline, consistent with relevance_filter.py pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Ruff pre-commit hook reformatted files on first commit attempt (trailing whitespace, formatting); re-staged and recommitted. No code logic changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Geographic filter ready for integration into Phase 4 Plan 03 (URL deduplication)
- Both filter stages (relevance + geo) are pure functions — compose cleanly in pipeline
- geo_tier field now populated on all articles passing both filters, ready for Phase 5 AI analysis
- No blockers; full suite at 106 tests, ruff clean

---
*Phase: 04-filtering-and-deduplication*
*Completed: 2026-02-28*
