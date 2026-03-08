---
phase: 10-advanced-bot-controls
plan: 03
subsystem: bot
tags: [nlp, claude-haiku, telegram, schedule, natural-language, anthropic]

requires:
  - phase: 10-advanced-bot-controls
    provides: BotState schema, pause/resume handlers, stats handler
provides:
  - NL intent parser with Claude Haiku classification (7 intent types)
  - Schedule modification and event scheduling handlers
  - All Phase 10 handlers wired into bot entrypoint
  - Updated /help with all new commands and NL mention
affects: [11-breaking-news-production]

tech-stack:
  added: [anthropic (Claude Haiku 4.5 for NL intent classification)]
  patterns: [NL dispatch map pattern, async executor for sync API calls, schedule_command_inner reusable core]

key-files:
  created:
    - src/pipeline/bot/nlp.py
    - src/pipeline/bot/schedule.py
    - tests/test_bot_nlp.py
    - tests/test_bot_schedule.py
  modified:
    - src/pipeline/bot/entrypoint.py
    - src/pipeline/bot/handler.py
    - tests/test_bot_entrypoint.py
    - tests/test_bot_handler.py

key-decisions:
  - "NL parser uses Claude Haiku 4.5 with structured JSON output, falls back to unknown on any failure"
  - "NL catch-all in group 2 (lowest priority) so slash commands and regex patterns always match first"
  - "Short messages (<6 chars) silently ignored to prevent 'ok' and 'hi' triggering API calls"
  - "schedule_command_inner extracted as reusable core for both /schedule command and NL dispatch"
  - "IST to UTC conversion uses simple 330-minute offset with modular day wrapping"
  - "Keyword NL dispatch provides guidance text (not auto-execution) to keep add/remove explicit"

patterns-established:
  - "NL dispatch map pattern: intent string -> async handler function lookup"
  - "asyncio.run_in_executor for sync Anthropic calls in async handler context"
  - "Handler group priority: 0 (commands) > 1 (unauthorized) > 2 (NL catch-all)"

requirements-completed: [BOT-07, BOT-08, BOT-09]

duration: 5min
completed: 2026-03-08
---

# Phase 10 Plan 03: NL Scheduling Summary

**Claude Haiku NL intent parser with 7 intent types, schedule modification/event handlers, and full Phase 10 entrypoint wiring with 489 tests passing**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-08T00:23:18Z
- **Completed:** 2026-03-08T00:28:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments
- NLIntent Pydantic model with 7 intent types (pause, resume, schedule_modify, event_schedule, keyword_add, keyword_remove, unknown) and parameter extraction
- parse_ist_time and ist_to_utc_cron for time parsing and IST/UTC conversion with edge cases
- /schedule command for viewing and modifying delivery times in bot_state.json
- create_event_schedule for event-based tracking entries
- All Phase 10 handlers (/pause, /resume, /stats, /schedule, NL catch-all) registered in entrypoint
- /help text updated with all new commands and natural language support mention

## Task Commits

Each task was committed atomically:

1. **Task 1: NL intent parser with Claude Haiku** - `03f6961` (feat)
2. **Task 2: Schedule modification and event scheduling handlers** - `2d0ea32` (feat)
3. **Task 3: Wire all Phase 10 handlers into entrypoint and update /help** - `4185289` (feat)

## Files Created/Modified
- `src/pipeline/bot/nlp.py` - NL intent parser with Claude Haiku, dispatch helpers, NLIntent model
- `src/pipeline/bot/schedule.py` - Schedule modification, event creation, IST time parsing
- `src/pipeline/bot/entrypoint.py` - Phase 10 handler registration, NL catch-all in group 2
- `src/pipeline/bot/handler.py` - Updated /help text with new commands and NL mention
- `tests/test_bot_nlp.py` - 19 tests for NL model, parsing, and handler dispatch
- `tests/test_bot_schedule.py` - 22 tests for time parsing, UTC conversion, schedule commands
- `tests/test_bot_entrypoint.py` - Updated handler count tests, group 2 NL handler test
- `tests/test_bot_handler.py` - 5 new tests for /pause, /resume, /stats, /schedule, NL in help

## Decisions Made
- NL parser uses Claude Haiku 4.5 with structured JSON output, falls back to unknown on any failure
- NL catch-all in group 2 (lowest priority) so slash commands and regex patterns always match first
- Short messages (<6 chars) silently ignored to prevent 'ok' and 'hi' triggering API calls
- schedule_command_inner extracted as reusable core for both /schedule command and NL dispatch
- IST to UTC conversion uses simple 330-minute offset with modular day wrapping
- Keyword NL dispatch provides guidance text (not auto-execution) to keep add/remove explicit

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. ANTHROPIC_API_KEY already configured from Phase 5.

## Next Phase Readiness
- Phase 10 complete: all advanced bot controls implemented (pause/resume, stats, NL parsing, schedule modification, event scheduling)
- 489 tests passing with zero regressions
- Ready for Phase 11: Breaking News and Production Hardening

---
*Phase: 10-advanced-bot-controls*
*Completed: 2026-03-08*
