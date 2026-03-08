---
phase: 11-breaking-news-production-hardening
plan: 01
subsystem: delivery
tags: [breaking-news, telegram, rss, keyword-scoring, ai-gate, github-actions]

# Dependency graph
requires:
  - phase: 04-filtering-and-deduplication
    provides: score_article keyword scoring, filter_duplicates dedup
  - phase: 05-ai-analysis-pipeline
    provides: classify_articles AI confirmation, cost_tracker budget gates
  - phase: 06-telegram-delivery
    provides: send_telegram_message, _escape_html formatting
  - phase: 10-advanced-bot-controls
    provides: BotState pause/resume state for pause guard
provides:
  - Breaking news pipeline (run_breaking, format_breaking_alert, breaking_filter)
  - Delivery window guard (_is_delivery_window)
  - Pause guard (_is_paused)
  - breaking.yml hourly GitHub Actions workflow
affects: [11-02, 11-03]

# Tech tracking
tech-stack:
  added: []
  patterns: [two-stage-filter, guard-pattern, lightweight-entrypoint]

key-files:
  created:
    - src/pipeline/breaking.py
    - .github/workflows/breaking.yml
  modified:
    - tests/test_breaking.py

key-decisions:
  - "Keyword score >= 80 threshold for breaking fast-path (same as AI fallback HIGH from Phase 5)"
  - "AI budget reserve at $3.00 (not $4.75) to preserve budget for scheduled runs"
  - "30-minute window guard around 7 AM and 4 PM IST prevents breaking-vs-scheduled collision"
  - "RSS-only fetch in breaking path (no GNews) to preserve daily quota for scheduled runs"
  - "Same concurrency group (deliver) as deliver.yml prevents git conflicts on seen.json"

patterns-established:
  - "Guard pattern: check config flag, pause state, delivery window before any I/O"
  - "Two-stage filter: cheap keyword pass then expensive AI confirmation"
  - "Lightweight entrypoint: reuses existing modules without duplicating logic"

requirements-completed: [DLVR-05]

# Metrics
duration: 5min
completed: 2026-03-08
---

# Phase 11 Plan 01: Breaking News Pipeline Summary

**Two-stage breaking news pipeline with keyword fast-path (>= 80), AI confirmation gate, pause/time guards, and hourly GitHub Actions workflow**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-08T06:21:43Z
- **Completed:** 2026-03-08T06:27:38Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Breaking news pipeline that fires hourly between scheduled deliveries for critical stories
- Two-stage filter: keyword fast-path (score >= 80) with optional AI confirmation (budget < $3.00)
- Three guards: breaking_news_enabled config flag, bot pause state, delivery window collision
- 30 new tests covering filter, dedup, AI gate, format, pause, time window, and integration
- 519 total tests passing (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Breaking news entrypoint with two-stage filter, guards, and alert formatter**
   - `79d55ff` (test: RED phase - failing tests)
   - `71a2de3` (feat: GREEN phase - implementation passing all 30 tests)
2. **Task 2: Breaking news GitHub Actions workflow** - `04f5b45` (chore)

_Note: Task 1 used TDD with RED/GREEN commits_

## Files Created/Modified
- `src/pipeline/breaking.py` - Breaking news entrypoint: run_breaking(), format_breaking_alert(), breaking_filter(), _is_delivery_window(), _is_paused()
- `tests/test_breaking.py` - 30 tests across 7 test classes (filter, dedup, AI gate, format, pause, time window, integration)
- `.github/workflows/breaking.yml` - Hourly cron workflow with same concurrency group as deliver.yml

## Decisions Made
- Keyword score threshold >= 80 for breaking news (matches Phase 5 AI fallback HIGH threshold)
- AI budget reserve at $3.00 (preserves $2 for scheduled runs; when exceeded, trusts keyword score)
- 30-minute delivery window guard around 7 AM and 4 PM IST prevents alert/brief collision
- RSS-only fetch (no GNews) to preserve the 25-call/day quota for scheduled runs
- Telegram-only delivery (no email) for breaking news speed
- Hourly cron (not */30) as safe default for private repos within 2000 min/month free tier
- Same concurrency group as deliver.yml to prevent git conflicts on seen.json

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed KeywordCategory constructor in test helper**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Test helper _make_keywords passed list directly to categories dict instead of KeywordCategory model
- **Fix:** Wrapped keyword lists in KeywordCategory(active=True, keywords=...) objects
- **Files modified:** tests/test_breaking.py
- **Verification:** All 30 tests pass
- **Committed in:** 71a2de3 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test helper needed schema-aware construction. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Breaking workflow uses the same secrets already configured for deliver.yml.

## Next Phase Readiness
- Breaking news pipeline complete and tested
- Ready for Plan 02 (Production hardening) and Plan 03 (remaining hardening)
- breaking.yml will activate automatically when pushed to GitHub

---
*Phase: 11-breaking-news-production-hardening*
*Completed: 2026-03-08*
