---
phase: 08-railway-bot-foundation
plan: 03
subsystem: bot
tags: [github-api, repository-dispatch, httpx-async, telegram-bot, on-demand-pipeline]

# Dependency graph
requires:
  - phase: 08-railway-bot-foundation
    provides: "Auth guard, /help, /status handlers, bot entrypoint with polling"
provides:
  - "trigger_pipeline function sending repository_dispatch to GitHub Actions"
  - "/run command handler with env var validation and user feedback"
  - "/run registered in entrypoint with auth filter"
  - "Complete bot feature set: auth guard, /help, /status, /run"
affects: [09-keyword-menu-management, 10-advanced-bot-controls, 11-breaking-news]

# Tech tracking
tech-stack:
  added: []
  patterns: [repository-dispatch-trigger, env-var-guard-before-api-call]

key-files:
  created:
    - src/pipeline/bot/dispatcher.py
    - tests/test_bot_dispatcher.py
  modified:
    - src/pipeline/bot/handler.py
    - src/pipeline/bot/entrypoint.py

key-decisions:
  - "httpx.AsyncClient(timeout=15.0) for dispatch -- longer timeout than status reads (10s) since dispatch is less latency-critical"
  - "Immediate 'Triggering...' feedback before API call -- user knows bot received command even if dispatch takes time"
  - "trigger_pipeline catches all exceptions and returns False -- handler never crashes, user gets failure message"

patterns-established:
  - "Env var guard pattern: check GITHUB_PAT/OWNER/REPO before any API call, reply with config error if missing"
  - "Two-message feedback: immediate acknowledgment then result -- keeps Telegram UX responsive"

requirements-completed: [INFRA-04]

# Metrics
duration: 3min
completed: 2026-03-07
---

# Phase 8 Plan 03: /run Command and Dispatch Trigger Summary

**Repository dispatch trigger for on-demand pipeline runs via /run Telegram command with env var guard and two-message feedback**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-07T11:53:35Z
- **Completed:** 2026-03-07T11:56:33Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments
- trigger_pipeline sends repository_dispatch POST to GitHub API, returns True on 204 / False on any error
- /run handler validates GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO env vars before dispatch
- Immediate "Triggering pipeline run..." feedback, then success/failure confirmation
- /run registered in entrypoint with auth filter alongside /help, /status, /start
- 15 new tests, 343 total passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Repository dispatch trigger and /run command** - `8d7bd3a` (test: RED), `80e7d10` (feat: GREEN)

_Note: TDD task has RED (failing test) then GREEN (implementation) commits._

## Files Created/Modified
- `src/pipeline/bot/dispatcher.py` - trigger_pipeline: async POST to GitHub dispatches API with Bearer auth
- `src/pipeline/bot/handler.py` - Added run_now_command with env var guard, trigger call, and result feedback
- `src/pipeline/bot/entrypoint.py` - Added /run CommandHandler registration with auth filter
- `tests/test_bot_dispatcher.py` - 15 tests: dispatch success/failure, payload validation, handler success/failure/missing env

## Decisions Made
- httpx.AsyncClient timeout=15.0 for dispatch (vs 10.0 in status reads) -- dispatch is write operation, slightly more lenient
- Immediate "Triggering..." reply before API call -- responsive UX even if GitHub API is slow
- trigger_pipeline returns bool (not raises) -- handler decides on user messaging, dispatcher stays pure

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None for this plan. Railway deployment env vars (TELEGRAM_BOT_TOKEN, AUTHORIZED_USER_IDS, GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO) documented in Phase 8 deployment context.

## Next Phase Readiness
- Phase 8 complete: Railway config (Plan 01), auth + /help + /status (Plan 02), /run dispatch (Plan 03)
- Full bot feature set ready for Railway deployment
- Phase 9 adds /keywords command for keyword management
- Phase 10 adds advanced bot controls (/config, /schedule)

## Self-Check: PASSED

All 4 key files verified present. Both task commits verified in git log. 343 tests passing (15 new). All imports verified working.

---
*Phase: 08-railway-bot-foundation*
*Completed: 2026-03-07*
