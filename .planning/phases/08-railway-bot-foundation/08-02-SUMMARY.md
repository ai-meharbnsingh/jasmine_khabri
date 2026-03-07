---
phase: 08-railway-bot-foundation
plan: 02
subsystem: bot
tags: [python-telegram-bot, authorization, github-api, httpx-async, polling]

# Dependency graph
requires:
  - phase: 08-railway-bot-foundation
    provides: "PipelineStatus schema, railway.json, python-telegram-bot dependency"
provides:
  - "Authorization guard loading user IDs from AUTHORIZED_USER_IDS env var"
  - "/help command listing available bot commands"
  - "/status command reading pipeline health from GitHub Contents API"
  - "Unauthorized catch-all rejecting unknown users"
  - "Bot entrypoint with Application builder and run_polling"
affects: [08-03, 09-keyword-menu-management, 10-advanced-bot-controls]

# Tech tracking
tech-stack:
  added: []
  patterns: [async-github-contents-api, filters-user-auth-guard, application-builder-polling]

key-files:
  created:
    - src/pipeline/bot/auth.py
    - src/pipeline/bot/status.py
    - src/pipeline/bot/entrypoint.py
    - tests/test_bot_auth.py
    - tests/test_bot_handler.py
    - tests/test_bot_entrypoint.py
  modified:
    - src/pipeline/bot/handler.py
    - src/pipeline/bot/__init__.py

key-decisions:
  - "filters.User(user_id=...) not user_ids -- python-telegram-bot v22 uses singular parameter name"
  - "asyncio.run() in sync tests for async handlers -- avoids pytest-asyncio dependency, simplest approach"
  - "Empty AUTHORIZED_USER_IDS falls back to filters.ALL with warning -- bot still functional for testing"
  - "fetch_pipeline_status returns default PipelineStatus on any failure -- never crashes the handler"

patterns-established:
  - "Async httpx in bot handlers: always httpx.AsyncClient, never sync httpx in python-telegram-bot callbacks"
  - "GitHub Contents API with raw Accept header for reading repo state files from Railway bot"
  - "Group=1 for unauthorized catch-all handler, group=0 (default) for authorized commands"

requirements-completed: [INFRA-04, BOT-01, BOT-02, BOT-11]

# Metrics
duration: 4min
completed: 2026-03-07
---

# Phase 8 Plan 02: Bot Core Commands and Entrypoint Summary

**Authorization guard with env-based user whitelist, /help and /status commands reading GitHub pipeline status, and Application entrypoint with polling**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-07T11:45:55Z
- **Completed:** 2026-03-07T11:50:09Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Authorization guard loads user IDs from AUTHORIZED_USER_IDS env var with whitespace/empty segment handling
- /help command returns formatted list of available commands (/help, /status, /run)
- /status command reads pipeline_status.json from GitHub Contents API and formats a health summary
- Unauthorized users get "Unauthorized. Access denied." response
- Bot entrypoint builds Application with auth-filtered handlers and starts polling
- 27 new tests, 328 total passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Authorization guard and /help + /status command handlers** - `85ec84e` (test: RED), `c648cb5` (feat: GREEN)
2. **Task 2: Bot entrypoint with Application builder and polling** - `d0abf03` (test: RED), `8d69314` (feat: GREEN)

_Note: TDD tasks have RED (failing test) then GREEN (implementation) commits._

## Files Created/Modified
- `src/pipeline/bot/auth.py` - load_authorized_users parsing AUTHORIZED_USER_IDS env var to set[int]
- `src/pipeline/bot/status.py` - read_github_file via Contents API, fetch_pipeline_status with fallback defaults
- `src/pipeline/bot/handler.py` - help_command, status_command, unauthorized_handler callbacks
- `src/pipeline/bot/entrypoint.py` - main() with ApplicationBuilder, auth filter, handler registration, run_polling
- `src/pipeline/bot/__init__.py` - Updated module docstring for Railway context
- `tests/test_bot_auth.py` - 6 tests for authorization guard
- `tests/test_bot_handler.py` - 14 tests for command handlers and GitHub status reader
- `tests/test_bot_entrypoint.py` - 7 tests for entrypoint construction and polling

## Decisions Made
- `filters.User(user_id=...)` is the correct parameter name in python-telegram-bot v22 (not `user_ids` as in the research doc)
- Used `asyncio.run()` in sync test methods instead of adding pytest-asyncio -- simplest approach, no new dependency
- Empty AUTHORIZED_USER_IDS falls back to `filters.ALL` with a warning log -- allows bot to run for testing without whitelist
- `fetch_pipeline_status` catches all exceptions and returns default PipelineStatus -- handler never crashes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed filters.User parameter name from user_ids to user_id**
- **Found during:** Task 2 (entrypoint implementation)
- **Issue:** Research doc and plan specified `filters.User(user_ids=set)` but python-telegram-bot v22 uses `user_id` (singular)
- **Fix:** Changed to `filters.User(user_id=authorized)` in entrypoint.py
- **Files modified:** src/pipeline/bot/entrypoint.py
- **Verification:** All 7 entrypoint tests pass
- **Committed in:** 8d69314 (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary API parameter name correction. No scope creep.

## Issues Encountered

None.

## User Setup Required

None for this plan. Railway deployment configuration (env vars: TELEGRAM_BOT_TOKEN, AUTHORIZED_USER_IDS, GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO) will be documented in Plan 03.

## Next Phase Readiness
- Auth guard, /help, /status, unauthorized handler all working and tested
- Bot entrypoint ready to run on Railway with polling
- Plan 03 adds /run command (repository_dispatch) and final deployment wiring
- `filters.User(user_id=...)` parameter name documented for Plan 03 reference

## Self-Check: PASSED

All 8 key files verified present. All 4 task commits verified in git log. 328 tests passing (27 new). All imports verified working.

---
*Phase: 08-railway-bot-foundation*
*Completed: 2026-03-07*
