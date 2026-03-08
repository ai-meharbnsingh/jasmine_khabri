---
phase: 11-breaking-news-production-hardening
plan: 02
subsystem: infra
tags: [pydantic, usage-tracking, monthly-reset, free-tier, github-api]

# Dependency graph
requires:
  - phase: 08-railway-bot-foundation
    provides: PipelineStatus schema, load/save_pipeline_status, /status command, fetch_pipeline_status
  - phase: 11-breaking-news-production-hardening
    provides: breaking.py run_breaking pipeline
provides:
  - Extended PipelineStatus with monthly usage tracking (deliver runs, breaking runs, alerts, Actions minutes)
  - Monthly reset logic in load_pipeline_status
  - Run counter increments in main.py and breaking.py
  - Free-tier usage display in /status command (Actions minutes, AI spend percentages)
  - fetch_ai_cost function in bot/status.py
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Monthly reset via model_copy in load_pipeline_status (same as load_ai_cost)"
    - "_save_breaking_status helper for consistent counter updates at all exit points"
    - "fetch_ai_cost follows fetch_pipeline_status pattern for GitHub API reads"

key-files:
  created: []
  modified:
    - src/pipeline/schemas/pipeline_status_schema.py
    - src/pipeline/utils/loader.py
    - src/pipeline/main.py
    - src/pipeline/breaking.py
    - src/pipeline/bot/handler.py
    - src/pipeline/bot/status.py
    - tests/test_pipeline_status.py
    - tests/test_main.py
    - tests/test_breaking.py
    - tests/test_bot_handler.py

key-decisions:
  - "Monthly reset in load_pipeline_status uses model_copy pattern matching load_ai_cost"
  - "_save_breaking_status helper called at all exit points after RSS fetch to always count runs"
  - "fetch_ai_cost in status.py reuses read_github_file pattern with graceful fallback"
  - "3.0 min estimate per deliver run, 1.5 min per breaking run for Actions budget tracking"
  - "Usage percentages: Actions against 2000 min free tier, AI against $5.00 budget"

patterns-established:
  - "Usage tracking via prev_status load-then-increment-then-save pattern"
  - "Free-tier monitoring displayed in /status with percentage calculations"

requirements-completed: [INFRA-06]

# Metrics
duration: 7min
completed: 2026-03-08
---

# Phase 11 Plan 02: Free-Tier Usage Tracking Summary

**Monthly usage tracking with auto-reset counters for Actions minutes and AI spend, surfaced as percentages in /status command**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-08T06:31:45Z
- **Completed:** 2026-03-08T06:39:00Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- PipelineStatus extended with 5 new fields (usage_month, monthly_deliver_runs, monthly_breaking_runs, monthly_breaking_alerts, est_actions_minutes) -- backward compatible
- Monthly reset in load_pipeline_status auto-zeroes counters on month boundary while preserving non-monthly fields
- main.py increments deliver run counter (+1 run, +3.0 est minutes) every pipeline run
- breaking.py increments breaking run counter (+1 run, +1.5 est minutes, +alerts_sent) at every exit point after RSS fetch
- /status now displays "Free Tier Usage" section with Actions minutes percentage (X/2000) and AI spend percentage ($X/$5.00)
- 21 new tests (537 total), all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend PipelineStatus schema with usage tracking and monthly reset** - `820b7b4` (feat)
2. **Task 2: Enhance /status command with free-tier usage percentages** - `ded9335` (feat)

_Note: TDD tasks -- RED tests written first, GREEN implementation, then committed together_

## Files Created/Modified
- `src/pipeline/schemas/pipeline_status_schema.py` - Added 5 usage tracking fields with defaults
- `src/pipeline/utils/loader.py` - Monthly reset logic in load_pipeline_status via model_copy
- `src/pipeline/main.py` - Load prev status, increment deliver run counter in PipelineStatus construction
- `src/pipeline/breaking.py` - _save_breaking_status helper increments breaking counters at all exit points
- `src/pipeline/bot/handler.py` - status_command fetches AI cost and displays usage percentages
- `src/pipeline/bot/status.py` - Added fetch_ai_cost function (same pattern as fetch_pipeline_status)
- `tests/test_pipeline_status.py` - TestUsageTracking (4 tests) and TestUsageReset (4 tests)
- `tests/test_main.py` - TestRunCounter (1 test)
- `tests/test_breaking.py` - TestBreakingRunCounter (2 tests)
- `tests/test_bot_handler.py` - TestStatusUsage (5 tests), TestStatusUsageNoData (1 test), TestStatusAICostFetch (1 test)

## Decisions Made
- Monthly reset in load_pipeline_status uses model_copy pattern (consistent with load_ai_cost)
- _save_breaking_status helper called at all exit points after RSS fetch to always count breaking runs, even when no alerts sent
- fetch_ai_cost reuses read_github_file and follows fetch_pipeline_status pattern with graceful AICost(month="") fallback
- Estimated 3.0 min per deliver run, 1.5 min per breaking run for Actions budget tracking
- Usage percentages calculated against 2000 min free tier (Actions) and $5.00 budget (AI)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 11 complete (both plans done) -- system is production-ready with breaking news and usage monitoring
- Pipeline is self-monitoring for free-tier compliance

---
*Phase: 11-breaking-news-production-hardening*
*Completed: 2026-03-08*
