---
phase: 09-keyword-and-menu-management
plan: 02
subsystem: bot
tags: [telegram-bot, inline-keyboard, callback-query, menu, python-telegram-bot]

# Dependency graph
requires:
  - phase: 09-keyword-and-menu-management
    provides: "keywords.py (format_keywords_display, ADD_PATTERN, REMOVE_PATTERN), github.py"
  - phase: 08-railway-bot-foundation
    provides: "Bot entrypoint, handler.py (help_command), status.py (fetch_pipeline_status, read_github_file), auth.py"
provides:
  - "Inline keyboard menu command (/menu) with Keywords, Status, Help buttons"
  - "CallbackQueryHandler routing button taps to content display"
  - "Updated entrypoint with all Phase 9 handlers registered"
  - "Updated /help text with /keywords, /menu, and add/remove syntax"
affects: [10-advanced-bot-controls]

# Tech tracking
tech-stack:
  added: []
  patterns: ["InlineKeyboardMarkup with InlineKeyboardButton for Telegram menus", "CallbackQueryHandler with pattern matching for button routing", "query.answer() + query.edit_message_text() for callback responses", "Defense-in-depth auth check in callback handler"]

key-files:
  created:
    - src/pipeline/bot/menu.py
    - tests/test_bot_menu.py
  modified:
    - src/pipeline/bot/entrypoint.py
    - src/pipeline/bot/handler.py
    - tests/test_bot_entrypoint.py
    - tests/test_bot_handler.py

key-decisions:
  - "InlineKeyboardMarkup with 2 rows: [Keywords, Status] and [Help] for clean layout"
  - "Defense-in-depth auth in callback handler using load_authorized_users() from auth.py"
  - "Empty AUTHORIZED_USER_IDS allows all users in callback (matches entrypoint pattern)"
  - "Status text in menu_callback duplicates handler.py format (no shared function) for isolation"

patterns-established:
  - "CallbackQueryHandler with pattern='^menu_' for prefixed callback routing"
  - "query.answer() always first in callback handler to dismiss Telegram loading spinner"
  - "query.edit_message_text() for in-place content replacement (no new messages)"

requirements-completed: [BOT-04]

# Metrics
duration: 5min
completed: 2026-03-07
---

# Phase 9 Plan 02: Inline Menu and Entrypoint Wiring Summary

**Inline keyboard menu with Keywords/Status/Help buttons, callback routing, and full Phase 9 handler registration in bot entrypoint**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-07T23:42:04Z
- **Completed:** 2026-03-07T23:47:19Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Inline keyboard /menu command with 3 buttons (Keywords, Status, Help) in 2-row layout
- Callback handler routing button taps to keyword display, pipeline status, and help text
- All Phase 9 handlers wired into entrypoint (keywords, menu, add, remove, callback)
- allowed_updates updated to include callback_query for inline keyboard support
- /help text updated with /keywords, /menu, and add/remove syntax documentation
- 22 new tests (16 menu + 6 entrypoint/handler), 403 total suite passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Inline keyboard menu command and callback handlers** - `a7863c4` (test) + `8795187` (feat)
2. **Task 2: Wire Phase 9 handlers into entrypoint and update help text** - `db4ee83` (test) + `1ca91ea` (feat)

_Note: TDD tasks with RED -> GREEN flow_

## Files Created/Modified
- `src/pipeline/bot/menu.py` - Inline keyboard menu_command and menu_callback handlers
- `src/pipeline/bot/entrypoint.py` - Phase 9 handler registration, callback_query in allowed_updates
- `src/pipeline/bot/handler.py` - Updated /help text with /keywords, /menu, add/remove syntax
- `tests/test_bot_menu.py` - 16 tests for keyboard layout, callback routing, auth, error handling
- `tests/test_bot_entrypoint.py` - 3 new tests for handler count, allowed_updates with callback_query
- `tests/test_bot_handler.py` - 3 new tests for /keywords, /menu, add/remove in help text

## Decisions Made
- InlineKeyboardMarkup with 2-row layout: [Keywords, Status] top row, [Help] bottom row
- Defense-in-depth auth check in callback handler re-validates user from AUTHORIZED_USER_IDS
- Empty AUTHORIZED_USER_IDS allows all users through callback (matches entrypoint fallback pattern)
- Status text in menu callback duplicates handler.py format for module isolation (no shared function)
- CallbackQueryHandler registered without auth_filter (defense-in-depth check inside handler instead)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 9 complete: keyword CRUD, inline menu, all handlers registered
- Bot supports /help, /status, /run, /keywords, /menu commands plus text-based add/remove
- Inline keyboard enables button-tap navigation without typing commands
- Ready for Phase 10 (Advanced Bot Controls)

## Self-Check: PASSED

All 6 files verified present. All 4 commit hashes verified in git log.

---
*Phase: 09-keyword-and-menu-management*
*Completed: 2026-03-07*
